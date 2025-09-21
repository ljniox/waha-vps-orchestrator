# WAHA Deployment Documentation

## Overview
This document outlines the complete deployment process for WAHA (WhatsApp HTTP API) on an ARM64 server with HTTPS access via Caddy reverse proxy.

## Architecture
- **Server**: ARM64 Linux
- **WAHA Container**: AMD64 image running on ARM64 via QEMU emulation
- **Reverse Proxy**: Caddy with automatic Let's Encrypt SSL certificates
- **Domain**: waha-core.niox.ovh
- **Port**: 8080 (internal), 443 (external HTTPS)

## Prerequisites

### System Requirements
- Docker and Docker Compose installed
- QEMU emulation for cross-architecture containers
- Open ports: 80, 443, 8080
- Domain name pointing to server IP

### Initial Setup
```bash
# Enable QEMU emulation for AMD64 containers on ARM64
docker run --privileged --rm tonistiigi/binfmt --install all

# Open firewall ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8080/tcp
```

## Deployment Steps

### 1. Create Project Directory
```bash
mkdir -p /home/ubuntu/waha
cd /home/ubuntu/waha
```

### 2. Create Environment File (.env)
Create `/home/ubuntu/waha/.env` with the following configuration:

```env
SERVICE_FQDN_WAHA=waha-core.niox.ovh
SERVICE_URL_WAHA=https://waha-core.niox.ovh
WAHA_BASE_URL=https://waha-core.niox.ovh
WAHA_DASHBOARD_ENABLED=true
WAHA_DASHBOARD_PASSWORD=Password!10
WAHA_DASHBOARD_USERNAME=ljniox
WAHA_LOG_FORMAT=JSON
WAHA_LOG_LEVEL=info
WAHA_MEDIA_STORAGE=LOCAL
WAHA_PRINT_QR=false
WHATSAPP_API_HOSTNAME=https://waha-core.niox.ovh
WHATSAPP_API_KEY=28C5435535C2487DAFBD1164B9CD4E34
WAHA_API_KEY_PLAIN=waha-secret-key-12345
WHATSAPP_DEFAULT_ENGINE=NOWEB
WHATSAPP_DOWNLOAD_MEDIA=true
WHATSAPP_FILES_FOLDER=/app/media
WHATSAPP_FILES_LIFETIME=0
WHATSAPP_SWAGGER_CONFIG_ADVANCED=true
WHATSAPP_SWAGGER_PASSWORD=WassProdt!2025
WHATSAPP_SWAGGER_USERNAME=admin
WAHA_REDIS_HOST=redis
WAHA_REDIS_PORT=6379
```

### 3. Create Docker Compose Configuration
Create `/home/ubuntu/waha/docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: waha-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  waha:
    image: devlikeapro/waha:latest
    platform: linux/amd64
    container_name: waha-core
    restart: always
    dns: [1.1.1.1, 8.8.8.8]
    logging:
      driver: json-file
      options: { max-size: "100m", max-file: "10" }
    ports:
      - "8080:3000"
    environment:
      - WAHA_DASHBOARD_ENABLED=true
      - WAHA_APPS_ENABLED=false
      - WAHA_DASHBOARD_USERNAME=${WAHA_DASHBOARD_USERNAME}
      - WAHA_DASHBOARD_PASSWORD=${WAHA_DASHBOARD_PASSWORD}
      - WHATSAPP_API_KEY=${WHATSAPP_API_KEY}
      - WAHA_API_KEY_PLAIN=${WAHA_API_KEY_PLAIN}
      - WAHA_REDIS_HOST=redis
      - WAHA_REDIS_PORT=6379
      - WAHA_LOG_FORMAT=${WAHA_LOG_FORMAT}
      - WAHA_LOG_LEVEL=${WAHA_LOG_LEVEL}
      - WHATSAPP_DEFAULT_ENGINE=${WHATSAPP_DEFAULT_ENGINE}
      - WAHA_PRINT_QR=${WAHA_PRINT_QR}
      - WHATSAPP_SWAGGER_USERNAME=${WHATSAPP_SWAGGER_USERNAME}
      - WHATSAPP_SWAGGER_PASSWORD=${WHATSAPP_SWAGGER_PASSWORD}
      - WAHA_MEDIA_STORAGE=${WAHA_MEDIA_STORAGE}
      - WHATSAPP_FILES_LIFETIME=${WHATSAPP_FILES_LIFETIME}
      - WHATSAPP_FILES_FOLDER=${WHATSAPP_FILES_FOLDER}
      - WHATSAPP_DOWNLOAD_MEDIA=${WHATSAPP_DOWNLOAD_MEDIA}
      - WHATSAPP_SWAGGER_CONFIG_ADVANCED=${WHATSAPP_SWAGGER_CONFIG_ADVANCED}
      - WHATSAPP_API_HOSTNAME=${WHATSAPP_API_HOSTNAME}
      - WAHA_BASE_URL=${WAHA_BASE_URL}
      - SERVICE_FQDN_WAHA=${SERVICE_FQDN_WAHA}
      - SERVICE_URL_WAHA=${SERVICE_URL_WAHA}
      - WAHA_HOSTNAME=0.0.0.0
      - WAHA_PORT=3000
    volumes:
      - ./sessions:/app/.sessions
      - ./media:/app/.media

networks:
  default:
    name: waha-network

volumes:
  redis_data:
```

### 4. Configure Caddy Reverse Proxy
Create `/etc/caddy/Caddyfile`:

```caddyfile
waha-core.niox.ovh {
    reverse_proxy localhost:8080 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }
    header {
        Strict-Transport-Security "max-age=31536000; includeSubdomains; preload"
    }
}
```

### 5. Start WAHA Service
```bash
cd /home/ubuntu/waha
docker compose down && docker compose up -d
```

### 6. Verify Deployment
```bash
# Check container status
docker ps

# Check logs
docker logs waha-core

# Test API with correct key
curl -H "X-Api-Key: 28C5435535C2487DAFBD1164B9CD4E34" https://waha-core.niox.ovh/api/sessions

# Test basic connectivity
curl -I https://waha-core.niox.ovh
```

## Access Points

### Dashboard
- **URL**: https://waha-core.niox.ovh
- **Username**: ljniox
- **Password**: Password!10

### API
- **Base URL**: https://waha-core.niox.ovh
- **API Key**: 28C5435535C2487DAFBD1164B9CD4E34
- **Key Format**: SHA512 hashed key for enhanced security

### Key Endpoints
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/default` - Get default session status
- `POST /api/sessions/default/start` - Start default session
- `POST /api/sessions/default/stop` - Stop default session

## Troubleshooting Guide

### 1. Architecture Compatibility Issues
**Problem**: `no matching manifest for linux/arm64/v8 in manifest list`

**Solution**: Enable QEMU emulation
```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

### 2. SSL Certificate Issues
**Problem**: Caddy unable to obtain Let's Encrypt certificates

**Solution**: 
- Ensure domain points to server IP
- Open ports 80 and 443
- Check Caddy configuration

### 3. API Authentication Issues
**Problem**: 401 Unauthorized errors despite correct API key

**Solution**: 
- Use the SHA512 hashed API key: `28C5435535C2487DAFBD1164B9CD4E34`
- Container supports both plain text and SHA512 formats
- Test API access with: `curl -H "X-Api-Key: 28C5435535C2487DAFBD1164B9CD4E34" https://waha-core.niox.ovh/api/sessions`

### 4. Boolean Environment Variable Issues
**Problem**: `parseBool got unexpected value - use "true" or "false" values`

**Solution**: 
- Change `WHATSAPP_DOWNLOAD_MEDIA=LOCAL` to `WHATSAPP_DOWNLOAD_MEDIA=true`
- Ensure all boolean values are `true` or `false`, not strings

### 5. Apps Functionality Issues
**Problem**: "Apps are disabled. Enable it by setting 'WAHA_APPS_ENABLED=True'"

**Current Status**: Apps functionality is disabled because it requires Redis configuration.

**Solution for Future Implementation**:
- Add Redis service to Docker Compose
- Configure Redis connection variables
- Set `WAHA_APPS_ENABLED=true`

### 6. Network Binding Issues (Blank Page)
**Problem**: Dashboard shows blank page with 502 Bad Gateway error

**Root Cause**: WAHA binds to IPv6 localhost ([::1]:3000) instead of all interfaces (0.0.0.0:3000)

**Solution**: 
Add network binding configuration to docker-compose.yml:
```yaml
environment:
  - WAHA_HOSTNAME=0.0.0.0
  - WAHA_PORT=3000
```

**Verification**:
```bash
# Test direct connection
curl -I http://localhost:8080

# Test HTTPS through Caddy
curl -I https://waha-core.niox.ovh
```

### 7. Session Creation Issues
**Problem**: Unable to create sessions or connect to WhatsApp

**Solution**:
- Verify default session exists: `GET /api/sessions/default`
- Start session: `POST /api/sessions/default/start`
- Check session status for QR code scanning

## Maintenance

### Backup Strategy
- Session data: `/home/ubuntu/waha/sessions/`
- Media files: `/home/ubuntu/waha/media/`
- Configuration files: `.env`, `docker-compose.yml`

### Restart Services
```bash
cd /home/ubuntu/waha
docker compose restart
```

### Update WAHA
```bash
cd /home/ubuntu/waha
docker compose pull
docker compose up -d
```

### Monitor Logs
```bash
# Real-time logs
docker logs -f waha-core

# Recent logs
docker logs waha-core --tail 50
```

## Security Considerations

1. **API Key Security**: Using SHA512 hashed API key (`28C5435535C2487DAFBD1164B9CD4E34`) for enhanced security.
2. **Dashboard Access**: Use strong passwords and consider IP whitelisting.
3. **SSL**: Always use HTTPS with valid certificates.
4. **Container Security**: Regular base image updates and security patches.

## Performance Notes

- ARM64 server running AMD64 container via QEMU emulation
- Performance impact is minimal for API workloads
- Consider native ARM64 images when available

## Future Enhancements

1. **Redis Integration**: Enable apps functionality by setting `WAHA_APPS_ENABLED=true` (Redis is already configured)
2. **Monitoring**: Add health checks and monitoring
3. **Backup Automation**: Implement automated backup solutions
4. **Scaling**: Consider multi-instance deployment with load balancing

## Current Status

✅ **Deployment Complete**: WAHA is successfully deployed and operational
- **API Access**: Working with SHA512 authentication
- **Dashboard**: Accessible via HTTPS with basic authentication
- **Redis**: Configured and running (apps functionality disabled)
- **Network Binding**: Fixed to listen on all interfaces (0.0.0.0:3000)
- **SSL**: Automated Let's Encrypt certificates via Caddy

**Active WhatsApp Session**: Default session is running and connected with status "WORKING"