Project Progress Log

Date: 2025-09-22

Summary
- Added brainstorming and architecture for WAHA Orchestrator + Runners.
- Deployed a local-only WAHA stack (no public ports) with Redis.
- Added and deployed a local Orchestrator (FastAPI) + NATS stack attached to WAHA network.
- Configured WAHA webhook via API to point to Orchestrator with secret header.
- Implemented minimal Runner (Python + NATS) and verified end-to-end execution and WhatsApp replies.

What’s in the repo
- brainstorming/
  - README.md: Architecture, flows, examples
  - waha-on-swfs-vps/: Working WAHA config and deployment notes
- deploy/
  - local-no-public/: WAHA + Redis (127.0.0.1:8080 only)
  - local-orchestrator/: WAHA + NATS + Orchestrator (local stack)
  - local-orchestrator-attach/: Orchestrator + NATS attached to existing WAHA network
- orchestrator/: FastAPI app bridging WAHA <-> NATS (send via /api/sendText)
- runner/: Minimal Python runner subscribing to runner.dev.jobs

Runtime state (local server)
- WAHA: docker compose up at deploy/local-no-public (127.0.0.1:8080)
- Orchestrator + NATS + Runner: docker compose up at deploy/local-orchestrator-attach
- Network: Orchestrator+Runner joined to external network waha-local-network to reach waha-core:3000

Credentials (local-only, for development)
- File: deploy/local-no-public/.env
  - WAHA_DASHBOARD_USERNAME=admin
  - WAHA_DASHBOARD_PASSWORD=<generated>
  - WHATSAPP_API_KEY=<generated>
- File: deploy/local-orchestrator-attach/.env
  - INCOMING_SECRET=<generated> (for X-Webhook-Secret)
  - WAHA_TOKEN mirrors WHATSAPP_API_KEY for X-Api-Key

Important: Secrets committed for convenience in local dev. For production, rotate secrets and move to env vars or a secret manager; add .env to .gitignore and purge commit history if needed.

Deployed stacks
1) WAHA (local-only)
   - Path: deploy/local-no-public
   - Ports: 127.0.0.1:8080 -> waha-core:3000
   - Auth: X-Api-Key: $WHATSAPP_API_KEY
   - Test:
     curl -H "X-Api-Key: $KEY" -H 'Content-Type: application/json' \
       -d '{"chatId":"<phone>@c.us","text":"hello","session":"default"}' \
       http://localhost:8080/api/sendText

2) Orchestrator + NATS + Runner (attached)
   - Path: deploy/local-orchestrator-attach
   - Services: nats, orchestrator, runner-dev
   - Orchestrator URL (from WAHA): http://orchestrator:8000/waha/webhook (no host port exposed)
   - Webhook header: X-Webhook-Secret: <INCOMING_SECRET>
   - WAHA send path: POST /api/sendText with JSON { chatId, text, session }

Behavior verified
- WAHA API: /api/sendText returns 201 PENDING for outgoing messages
- Webhook: WAHA -> Orchestrator events accepted (HTTP 200) when header set
- Orchestrator replies: sends via /api/sendText; WAHA logs 201
- Runner: receives jobs on runner.dev.jobs and runs commands (e.g., node -v)
- WhatsApp: receives “Queued job …” and output chunks as fenced code blocks

WhatsApp command grammar supported
- /exec host=dev cmd="node -v"
- /exec host=dev cmd="python -V"
- /run host=dev "<prompt>"
- /logs <jobId>
- /stop <jobId> (stubbed end-to-end; runner stop not yet implemented)

Operational commands
- Start WAHA: (cd deploy/local-no-public && docker compose up -d)
- Start Orchestrator+NATS+Runner: (cd deploy/local-orchestrator-attach && docker compose up -d --build)
- Logs:
  - docker logs -f waha-core
  - docker logs -f orchestrator
  - docker logs -f runner-dev

Known items / next steps
- WAHA retries without secret show 403 until retries stop (harmless).
- NOWEB store warnings in WAHA are unrelated to webhooks; can enable store if needed.
- Implement /stop: add runner signal handling to terminate processes.
- Optional sandbox: run job commands inside a Docker toolchain image for isolation.
- Secrets hygiene: rotate keys, remove .env from VCS, and purge secrets from git history if promoting beyond local dev.

