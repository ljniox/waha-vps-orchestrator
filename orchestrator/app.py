import os
import json
import asyncio
import uuid
import shlex
import time
from typing import Dict, Any, Optional, List

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks

try:
    from nats.aio.client import Client as NATS
except Exception:  # type: ignore
    NATS = None  # allow import in non-runtime contexts


# WAHA config (local-only default)
WAHA_BASE_URL = os.getenv("WAHA_BASE_URL", "http://waha:3000")
WAHA_TOKEN = os.getenv("WAHA_TOKEN", "replace_me")
# WAHA outbound message endpoint is implementation-specific; make it configurable
WAHA_SEND_PATH = os.getenv("WAHA_SEND_PATH", "/api/messages/send")
WAHA_CHAT_KEY = os.getenv("WAHA_CHAT_KEY", "chatId")
WAHA_TEXT_KEY = os.getenv("WAHA_TEXT_KEY", "message")

# Webhook protection
INCOMING_SECRET = os.getenv("INCOMING_SECRET", "replace_me")

# NATS bus
BUS_URL = os.getenv("BUS_URL", "nats://nats:4222")

app = FastAPI()


JOBS: Dict[str, Dict[str, Any]] = {}
LOG_BUFFERS: Dict[str, List[str]] = {}
LAST_SEND_TS: Dict[str, float] = {}
NATS_CLIENT: Optional["NATS"] = None


def _headers() -> Dict[str, str]:
    # WAHA example expects X-Api-Key
    return {"X-Api-Key": WAHA_TOKEN}


async def send_whatsapp_text(chat_id: str, text: str):
    payload = {WAHA_CHAT_KEY: chat_id, WAHA_TEXT_KEY: text}
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{WAHA_BASE_URL}{WAHA_SEND_PATH}"
        r = await client.post(url, json=payload, headers=_headers())
        r.raise_for_status()


def authorize(req: Request):
    secret = req.headers.get("X-Webhook-Secret")
    if secret != INCOMING_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")


def parse_command(text: str) -> Dict[str, Any]:
    parts = text.strip().split()
    if not parts:
        return {"type": "noop"}
    head = parts[0].lower()
    if head == "/hosts":
        return {"type": "hosts"}
    if head == "/logs" and len(parts) >= 2:
        return {"type": "logs", "job_id": parts[1]}
    if head == "/stop" and len(parts) >= 2:
        return {"type": "stop", "job_id": parts[1]}
    if head == "/exec":
        # /exec host=<id> cmd="pytest -q"
        args = " ".join(parts[1:])
        host = "dev"
        cmd = None
        for token in shlex.split(args):
            if token.startswith("host="):
                host = token.split("=", 1)[1]
            if token.startswith("cmd="):
                cmd = token.split("=", 1)[1].strip('"')
        return {"type": "exec", "host": host, "cmd": cmd}
    if head == "/run":
        # /run host=<id> "<prompt>"
        host = "dev"
        prompt = text[len("/run"):].strip()
        for token in parts[1:]:
            if token.startswith("host="):
                host = token.split("=", 1)[1]
        if '"' in prompt:
            try:
                prompt = shlex.split(prompt)[0 if prompt.startswith('"') else 1]
            except Exception:
                pass
        return {"type": "run", "host": host, "prompt": prompt}
    return {"type": "noop"}


def allowlisted(cmd: List[str]) -> bool:
    allow = set((os.getenv("ALLOWLIST", "cc cookiecutter git gh pnpm npm node python uv pip pytest supabase docker").split()))
    return bool(cmd) and cmd[0] in allow


async def nats_connect():
    global NATS_CLIENT
    if NATS is None:
        return None
    nc = NATS()
    await nc.connect(servers=[BUS_URL])
    NATS_CLIENT = nc

    async def logs_handler(msg):
        subject = msg.subject
        data = msg.data.decode(errors="ignore")
        # subject example: runner.dev.logs.9c80a2
        parts = subject.split(".")
        job_id = parts[-1] if parts else "unknown"
        LOG_BUFFERS.setdefault(job_id, []).append(data.rstrip())

    async def done_handler(msg):
        data = msg.data.decode(errors="ignore")
        try:
            job_id, rc = data.split("|", 1)
        except ValueError:
            return
        JOBS[job_id] = {**JOBS.get(job_id, {}), "status": f"exit-{rc}"}

    await nc.subscribe("runner.*.logs.*", cb=logs_handler)
    await nc.subscribe("runner.*.done", cb=done_handler)
    return nc


async def flush_loop():
    while True:
        now = time.time()
        for job_id, lines in list(LOG_BUFFERS.items()):
            last = LAST_SEND_TS.get(job_id, 0)
            if lines and (now - last >= 2 or len(lines) >= 12):
                chunk = "\n".join(lines[:12])
                LOG_BUFFERS[job_id] = lines[12:]
                chat_id = JOBS.get(job_id, {}).get("chatId")
                if chat_id:
                    await send_whatsapp_text(chat_id, f"```{chunk}```")
                LAST_SEND_TS[job_id] = now
        await asyncio.sleep(1.0)


@app.on_event("startup")
async def on_start():
    await nats_connect()
    asyncio.create_task(flush_loop())


@app.post("/waha/webhook")
async def waha_webhook(request: Request, background: BackgroundTasks):
    authorize(request)
    body = await request.json()
    msg = body.get("messages", [{}])[0]
    chat_id = msg.get("chatId") or msg.get("from")
    text = (msg.get("text", {}) or {}).get("body") or msg.get("text") or ""
    if not chat_id:
        raise HTTPException(400, "missing chat_id")

    action = parse_command(text)
    if action["type"] == "noop":
        return {"ok": True}

    if action["type"] == "logs":
        job = JOBS.get(action["job_id"])
        await send_whatsapp_text(chat_id, json.dumps(job or {}, indent=2))
        return {"ok": True}

    if action["type"] == "stop":
        # publish a stop signal
        job_id = action["job_id"]
        if NATS_CLIENT:
            await NATS_CLIENT.publish("runner.control.stop", f"{job_id}".encode())
        await send_whatsapp_text(chat_id, f"Stop requested for {job_id}")
        return {"ok": True}

    if action["type"] == "exec":
        host = action["host"]
        cmd_str = action.get("cmd") or ""
        cmd = shlex.split(cmd_str)
        if not allowlisted(cmd):
            await send_whatsapp_text(chat_id, "Command not allowed.")
            return {"ok": False}
        job_id = uuid.uuid4().hex[:6]
        JOBS[job_id] = {"status": "running", "cmd": cmd_str, "chatId": chat_id}
        envelope = {
            "jobId": job_id,
            "runnerId": host,
            "cwd": None,
            "cmd": cmd,
            "env": {},
            "timeoutSec": 1800,
            "sandbox": "host",
        }
        if NATS_CLIENT:
            await NATS_CLIENT.publish(f"runner.{host}.jobs", json.dumps(envelope).encode())
        await send_whatsapp_text(chat_id, f"Queued job `{job_id}`: {cmd_str}")
        return {"ok": True}

    if action["type"] == "run":
        host = action["host"]
        prompt = (action.get("prompt") or "").strip('"')
        cmd = ["cc", "run", "--prompt", prompt]
        if not allowlisted(cmd):
            await send_whatsapp_text(chat_id, "Command not allowed.")
            return {"ok": False}
        job_id = uuid.uuid4().hex[:6]
        JOBS[job_id] = {"status": "running", "cmd": " ".join(cmd), "chatId": chat_id}
        envelope = {
            "jobId": job_id,
            "runnerId": host,
            "cwd": None,
            "cmd": cmd,
            "env": {},
            "timeoutSec": 1800,
            "sandbox": "host",
        }
        if NATS_CLIENT:
            await NATS_CLIENT.publish(f"runner.{host}.jobs", json.dumps(envelope).encode())
        await send_whatsapp_text(chat_id, f"Queued job `{job_id}`.")
        return {"ok": True}

    return {"ok": True}

