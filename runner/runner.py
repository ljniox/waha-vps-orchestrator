import os
import asyncio
import json
import shlex
from typing import List, Dict, Optional

from nats.aio.client import Client as NATS

RUNNER_ID = os.getenv("RUNNER_ID", "dev")
BUS_URL = os.getenv("BUS_URL", "nats://nats:4222")
ALLOW = set((os.getenv(
    "ALLOWLIST",
    "cc cookiecutter git gh pnpm npm node python uv pip pytest supabase docker"
).split()))


def allowlisted(cmd: List[str]) -> bool:
    return bool(cmd) and cmd[0] in ALLOW


async def exec_and_stream(nc: NATS, job: Dict[str, any]):
    job_id = job.get("jobId")
    cmd: List[str] = job.get("cmd") or []
    cwd: Optional[str] = job.get("cwd")
    if not allowlisted(cmd):
        await nc.publish(f"runner.{RUNNER_ID}.logs.{job_id}".encode(), b"command not allowed")
        await nc.publish(f"runner.{RUNNER_ID}.done".encode(), f"{job_id}|exit-126".encode())
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        async def pump(stream, label: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                await nc.publish(
                    f"runner.{RUNNER_ID}.logs.{job_id}".encode(),
                    f"{label} {line.decode(errors='ignore')}".encode(),
                )

        await asyncio.gather(pump(proc.stdout, "▸"), pump(proc.stderr, "!"))
        rc = await proc.wait()
        await nc.publish(
            f"runner.{RUNNER_ID}.done".encode(), f"{job_id}|{rc}".encode()
        )
    except Exception as e:
        await nc.publish(
            f"runner.{RUNNER_ID}.logs.{job_id}".encode(), f"! error: {e}".encode()
        )
        await nc.publish(
            f"runner.{RUNNER_ID}.done".encode(), f"{job_id}|exit-1".encode()
        )


async def main():
    nc = NATS()
    await nc.connect(servers=[BUS_URL])

    async def handler(msg):
        try:
            job = json.loads(msg.data.decode())
        except Exception:
            return
        asyncio.create_task(exec_and_stream(nc, job))

    await nc.subscribe(f"runner.{RUNNER_ID}.jobs", cb=handler)
    # Keep the runner alive
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())

