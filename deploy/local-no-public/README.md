Local WAHA Deployment (No Public URL)

Overview
- Runs WAHA and Redis locally with no public exposure.
- Based strictly on the technical setup from brainstorming/waha-on-swfs-vps.
- Ports bind to 127.0.0.1 only; access via localhost.

Prerequisites
- Docker and Docker Compose installed
- If host is ARM64 and image is AMD64, enable QEMU:
  docker run --privileged --rm tonistiigi/binfmt --install all

Setup
1) Copy env template and edit values:
   cp .env.example .env
   # set WAHA_DASHBOARD_PASSWORD, WHATSAPP_API_KEY, etc.

2) Start services:
   docker compose up -d

3) Verify containers:
   docker ps
   docker logs waha-core --tail 50

Access (local only)
- Dashboard: http://localhost:8080
- API base: http://localhost:8080
- Auth header: X-Api-Key: <WHATSAPP_API_KEY>

Examples
- List sessions:
  curl -H "X-Api-Key: <KEY>" http://localhost:8080/api/sessions

- Default session status:
  curl -H "X-Api-Key: <KEY>" http://localhost:8080/api/sessions/default

- Start default session:
  curl -X POST -H "X-Api-Key: <KEY>" http://localhost:8080/api/sessions/default/start

Notes
- The compose binds WAHA to 127.0.0.1:8080; nothing is exposed publicly.
- WAHA connects to Redis internally on the compose network.
- Keep boolean envs as true/false, not strings.

Maintenance
- Restart: docker compose restart
- Update:  docker compose pull && docker compose up -d
- Logs:    docker logs -f waha-core

