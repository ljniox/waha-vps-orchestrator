Local Orchestrator + NATS + WAHA (No Public URL)

Summary
- Runs NATS (JetStream), WAHA, and an Orchestrator API locally only.
- All ports bind to 127.0.0.1; nothing exposed publicly.
- Orchestrator accepts WAHA webhooks and dispatches jobs to NATS.

Layout
- nats: message bus (internal only)
- redis: backing store for WAHA
- waha: WhatsApp HTTP API (X-Api-Key auth)
- orchestrator: FastAPI app bridging WAHA <-> NATS

Prereqs
- Docker + Docker Compose
- If ARM64 host with AMD64 WAHA image, enable QEMU:
  docker run --privileged --rm tonistiigi/binfmt --install all

Setup
1) Copy env template and edit secrets:
   cp .env.example .env
   # set WHATSAPP_API_KEY, WAHA_DASHBOARD_PASSWORD, INCOMING_SECRET, etc.

2) Start stack:
   docker compose up -d --build

3) Verify:
   docker ps
   curl -I http://localhost:8080    # WAHA dashboard
   curl -I http://localhost:8000    # Orchestrator

Webhook wiring (local)
- Point WAHA’s webhook to Orchestrator: http://orchestrator:8000/waha/webhook (inside network)
- If configuring via UI/Swagger, you can temporarily set webhook to http://localhost:8000/waha/webhook (requests come from WAHA container; it must reach Orchestrator by name). Prefer setting WAHA envs or using its API to configure webhook if supported by your build.
- The Orchestrator expects header X-Webhook-Secret = ${INCOMING_SECRET}

WAHA outbound send
- The Orchestrator posts to `${WAHA_BASE_URL}${WAHA_SEND_PATH}` with header `X-Api-Key: ${WAHA_TOKEN}`.
- Payload keys configurable via env: `${WAHA_CHAT_KEY}` and `${WAHA_TEXT_KEY}` (default chatId/message).
- Adjust `WAHA_SEND_PATH` to your build’s send-message endpoint.

WhatsApp commands (examples)
- /exec host=dev cmd="node -v"
- /run host=dev "add tests for auth"
- /logs <jobId>
- /stop <jobId>

Notes
- This stack is local-only. Ports 8080 (WAHA) and 8000 (Orch) bind to 127.0.0.1.
- Runners live on other VPS instances and connect to NATS at `nats://<host>:4222`. For local tests, run a runner on the same network.

Troubleshooting
- 401 from WAHA: ensure `WHATSAPP_API_KEY` matches what WAHA expects; header is `X-Api-Key`.
- Send endpoint mismatch: open WAHA Swagger at http://localhost:8080 and verify the correct send-message path and payload.
- No logs relayed: ensure a runner publishes to `runner.<id>.logs.<jobId>` and `runner.<id>.done`.

