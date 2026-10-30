# SENTRIX Production Deployment & Operations Guide

> **Enterprise Deployment Guide for Production Infrastructures, Cloud Environments, and SOC Deployments.**

This guide covers production deployment architectures, container orchestration, bare-metal operations, database migrations, security hardening, monitoring, and disaster recovery for **SENTRIX — Intelligent DDoS Detection, Monitoring & Defense Platform**.

---

## 1. Deployment Architecture

SENTRIX is structured for high availability, security isolation, and controlled edge enforcement:

```mermaid
flowchart TD
    subgraph Internet_Edge["Public Internet & Edge Network"]
        Clients["Internet Users & Attackers"]
        CDN["AWS CloudFront CDN / AWS Shield"]
        KinesisStream["Amazon Kinesis Data Streams\n(sentrix-cloudfront-realtime-logs)"]
    end

    subgraph Demilitarized_Zone["Reverse Proxy & Ingress Layer"]
        NginxProxy["Nginx / Caddy Edge Gateway\n(SSL Termination, Port 443)"]
    end

    subgraph Application_Tier["Internal Application Network"]
        Frontend["SENTRIX Next.js 16 Web Dashboard\n(Standalone Container, Port 3000)"]
        Backend["SENTRIX FastAPI Control Plane\n(Uvicorn ASGI Container, Port 8000)"]
        KinesisWorker["SENTRIX Kinesis Worker Service\n(Dedicated Container / Process)"]
    end

    subgraph Data_Tier["Durable Persistence Tier"]
        DB[(PostgreSQL 15+ / Supabase / Amazon RDS\nwith SSL & Connection Pooling)]
    end

    Clients --> CDN
    CDN -->|Real-Time Access Logs| KinesisStream
    CDN -->|Web Traffic| NginxProxy

    NginxProxy -->|Dashboard UI /api/proxy| Frontend
    Frontend -->|Internal RPC| Backend
    NginxProxy -->|Direct Ingress API| Backend

    KinesisStream -->|Batch Shard Polling| KinesisWorker
    KinesisWorker -->|Telemetry & Deduplication| DB
    Backend -->|Checkpoints, Rules, Audits| DB
```

### Core Architecture Components:
1. **Frontend Presentation (Next.js 16 Standalone):** High-performance, lightweight UI running on Node.js 20 Alpine in non-root mode. Communicates with the backend via internal server proxy (`/api/proxy`) to keep authentication secrets off browser bundles.
2. **Backend Control Plane (FastAPI + Uvicorn):** Serves REST endpoints for real-time telemetry processing, EWMA anomaly scoring, Random Forest inference, rule staging, and configuration export.
3. **Dedicated Kinesis Worker (`app.workers.kinesis_worker`):** Autonomous background consumer dedicated to polling Amazon Kinesis Data Streams for CloudFront real-time access logs.
4. **Relational Database (PostgreSQL 15+):** Stores durable Kinesis shard checkpoints, threat alerts, staged mitigation rules, and regulatory audit events.

---

## 2. Production Prerequisites

Before deploying SENTRIX to production, ensure you have:
1. **Compute Infrastructure:** Dedicated Linux server or virtual machine running Ubuntu 22.04 LTS, Debian 12, Amazon Linux 2023, or a managed container orchestrator (AWS ECS, EKS, Docker Swarm, Nomad).
2. **Domain & DNS:** A fully qualified domain name (FQDN), e.g., `sentrix.yourdomain.com`, pointing to your server's public IP address.
3. **AWS IAM Credentials / Role:** If ingesting CloudFront real-time access logs, an IAM Role or IAM User with read permissions to your Amazon Kinesis Data Stream.
4. **PostgreSQL Database:** Provisioned PostgreSQL instance (Amazon RDS, Supabase, Neon, or self-hosted) accessible from the application tier.
5. **TLS/SSL Certificates:** Let's Encrypt automated certificates or corporate Wildcard certificates.

---

## 3. Server Hardware Sizing

| Metric | Minimum (Proof of Concept) | Recommended (Standard SOC) | High-Throughput (Enterprise) |
| :--- | :---: | :---: | :---: |
| **vCPU** | 2 Cores | 4 Cores | 8–16 Cores |
| **RAM** | 4 GB | 8 GB | 16–32 GB |
| **Disk Space** | 20 GB SSD | 50 GB NVMe SSD | 200 GB NVMe SSD |
| **Network** | 100 Mbps | 1 Gbps | 10 Gbps |
| **Throughput Target**| $\le 2,000$ RPS | $10,000$ RPS | $50,000+$ RPS |

---

## 4. Production Environment Configuration

Create a production `.env` file in the project root:

```ini
# ==============================================================================
# SENTRIX Production Environment Configuration
# ==============================================================================

# Application Environment
APP_ENV=production

# Production Database (PostgreSQL with connection pooling)
DATABASE_URL=postgresql://sentrix_user:STRONG_PASSWORD@db.yourdomain.internal:5432/sentrix_db

# Machine Learning Artifact Path
MODEL_PATH=models/approved_model.joblib

# API Authentication & Hardening (MANDATORY IN PRODUCTION)
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=8f3c7e4b9a1d2f6e5c8b7a0d4e3f2a1b5c8d7e9f0a2b4c6d8e1f3a5b7c9d0e2f

# Keepalive Secret for Free-Tier / Managed Database Anti-Pausing
KEEPALIVE_SECRET=7b2e9d4a1c8f3e5b0a7d9c2e4f6a8b1c

# AWS CloudFront & Amazon Kinesis Data Streams Integration
AWS_REGION=ap-south-1
AWS_KINESIS_STREAM_NAME=sentrix-cloudfront-realtime-logs
AWS_KINESIS_CONSUMER_ENABLED=false
AWS_KINESIS_BATCH_SIZE=1000
AWS_KINESIS_POLL_INTERVAL_SECONDS=1.0
AWS_KINESIS_ITERATOR_TYPE=LATEST

# Optional Static AWS Credentials (leave blank if running with attached IAM EC2/ECS role)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=

# CORS Origins (Comma-separated exact origins; *.vercel.app is allowed automatically)
CORS_ORIGINS=https://sentrix.yourdomain.com

# Frontend Server Configuration
NODE_ENV=production
NEXT_PUBLIC_USE_PROXY=true
BACKEND_URL=http://backend:8000
PORT=3000
```

> [!IMPORTANT]
> Always generate cryptographic tokens using `openssl rand -hex 32`. Never commit `.env` to version control.

---

## 5. Database Provisioning & Initialization

SENTRIX supports PostgreSQL 15+ for production durability and multi-process concurrency.

### Step 5.1: Create Dedicated PostgreSQL Database & User
Connect to your PostgreSQL cluster as superuser:
```sql
CREATE USER sentrix_user WITH ENCRYPTED PASSWORD 'STRONG_DB_PASSWORD';
CREATE DATABASE sentrix_db OWNER sentrix_user;
GRANT ALL PRIVILEGES ON DATABASE sentrix_db TO sentrix_user;
```

### Step 5.2: Execute Database Migrations
Run Alembic migrations to build tables and idempotent indices:
```bash
# Run migrations using the production DATABASE_URL
alembic -c backend/alembic.ini upgrade head
```

Verify that the following tables exist:
- `observations`
- `detections`
- `alerts`
- `mitigations`
- `threshold_configs`
- `audit_events`
- `simulation_runs`
- `simulation_ticks`
- `cloudfront_kinesis_events`
- `kinesis_checkpoints`

---

## 6. Docker Image Build Process

SENTRIX includes production-hardened, multi-stage Dockerfiles for both backend and frontend:

### Build Backend Image:
```bash
docker build \
  -t sentrix-backend:latest \
  -f backend/Dockerfile .
```
- **Builder Stage:** Uses `python:3.11-slim` with build tools to compile dependencies.
- **Runner Stage:** Minimal runtime containing only runtime dependencies (`libpq5`), non-root system user `sentrix` (UID `10001`), and healthcheck probes.

### Build Frontend Image:
```bash
docker build \
  -t sentrix-frontend:latest \
  -f frontend/Dockerfile .
```
- **Deps Stage:** `node:20-alpine` runs `npm ci` for dependency caching.
- **Builder Stage:** Runs `next build` producing a standalone output bundle in `.next/standalone`.
- **Runner Stage:** Minimal Alpine image running under non-root user `nextjs` (UID `1001`) serving on port 3000.

---

## 7. Docker Compose Deployment Procedure

### Step 7.1: Verify `docker-compose.yml`
Ensure persistent storage volumes and bridge networks are declared:
```bash
# Check configuration syntax
docker compose config
```

### Step 7.2: Deploy Services
Launch core backend and frontend services:
```bash
docker compose up -d --build
```

### Step 7.3: Deploy Dedicated Kinesis Worker (AWS Integration)
If streaming CloudFront real-time access logs from Amazon Kinesis, start the dedicated worker container via Docker Compose profiles:
```bash
docker compose --profile aws-worker up -d
```

### Step 7.4: Verify Container Health
```bash
docker compose ps
```
Both `sentrix-backend` and `sentrix-frontend` should report `(healthy)`.

Inspect logs:
```bash
# Backend logs
docker compose logs -f backend

# Frontend logs
docker compose logs -f frontend

# Kinesis worker logs
docker compose logs -f kinesis-worker
```

---

## 8. Non-Docker Deployment (Bare-Metal / Systemd)

For bare-metal Linux servers or virtual machines, run SENTRIX as managed `systemd` services.

### Step 8.1: Create Dedicated System User
```bash
sudo useradd -r -s /bin/false -m -d /opt/sentrix sentrix
sudo mkdir -p /opt/sentrix/app
sudo chown -R sentrix:sentrix /opt/sentrix
```

### Step 8.2: Setup Backend Virtual Environment
```bash
cd /opt/sentrix/app
git clone https://github.com/your-org/DDoS-Detection-and-Mitigation-Simulator.git .
python3 -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
alembic -c backend/alembic.ini upgrade head
```

### Step 8.3: Build Frontend
```bash
cd /opt/sentrix/app/frontend
npm ci
npm run build
```

### Step 8.4: Create Systemd Service Files

#### 1. Backend Service (`/etc/systemd/system/sentrix-backend.service`):
```ini
[Unit]
Description=SENTRIX Autonomous Defense Backend
After=network.target postgresql.service

[Service]
Type=simple
User=sentrix
Group=sentrix
WorkingDirectory=/opt/sentrix/app
EnvironmentFile=/opt/sentrix/app/.env
ExecStart=/opt/sentrix/app/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
Restart=always
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

#### 2. Kinesis Worker Service (`/etc/systemd/system/sentrix-kinesis.service`):
```ini
[Unit]
Description=SENTRIX CloudFront Kinesis Streaming Worker
After=network.target sentrix-backend.service

[Service]
Type=simple
User=sentrix
Group=sentrix
WorkingDirectory=/opt/sentrix/app
EnvironmentFile=/opt/sentrix/app/.env
ExecStart=/opt/sentrix/app/.venv/bin/python -m app.workers.kinesis_worker
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

#### 3. Frontend Service (`/etc/systemd/system/sentrix-frontend.service`):
```ini
[Unit]
Description=SENTRIX Next.js SOC Dashboard
After=network.target sentrix-backend.service

[Service]
Type=simple
User=sentrix
Group=sentrix
WorkingDirectory=/opt/sentrix/app/frontend
EnvironmentFile=/opt/sentrix/app/.env
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Step 8.5: Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sentrix-backend.service
sudo systemctl enable --now sentrix-kinesis.service
sudo systemctl enable --now sentrix-frontend.service
```

---

## 9. Reverse Proxy Configuration

Deploy Nginx or Caddy on the edge server to handle SSL termination, request buffering, and path routing.

### Nginx Configuration (`/etc/nginx/sites-available/sentrix.conf`):
```nginx
# Upstream clusters
upstream sentrix_frontend {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream sentrix_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name sentrix.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sentrix.yourdomain.com;

    # SSL Certificates
    ssl_certificate /etc/letsencrypt/live/sentrix.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sentrix.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max body size for telemetry batches
    client_max_body_size 25M;

    # Backend API routing
    location /api/ {
        proxy_pass http://sentrix_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Frontend UI routing
    location / {
        proxy_pass http://sentrix_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/sentrix.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 10. Automated SSL/TLS Configuration (Let's Encrypt)

Obtain free, automated SSL certificates via Certbot:
```bash
sudo apt update && sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d sentrix.yourdomain.com --agree-tos --email admin@yourdomain.com
```

Certbot installs an automated systemd timer (`certbot.timer`) that tests certificate renewal twice daily.

---

## 11. Production Security Hardening Checklist

- [x] **API Authentication:** Verify `API_AUTH_REQUIRED=true` and confirm requests without `Authorization: Bearer <TOKEN>` return `401 Unauthorized`.
- [x] **Protected Infrastructure Allowlist:** Ensure default allowlisted networks (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`) are active.
- [x] **Non-Root Containers:** Confirm containers run under UID `10001` (backend) and UID `1001` (frontend).
- [x] **CORS Origin Restriction:** Ensure `CORS_ORIGINS` specifies exact production hostnames.
- [x] **Single-Worker Enforcement:** Confirm backend runs with `--workers 1` to preserve process-local state consistency until distributed caching is added.
- [x] **Kinesis Sequence Regex Validation:** Guard active against non-numeric shard sequence injections.

---

## 12. Health Checks & Monitoring

### 1. Public Health Check:
```bash
curl -i https://sentrix.yourdomain.com/api/v1/health
```
Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-10-30T10:00:00.000000Z",
  "version": "0.1.0",
  "environment": "production"
}
```

### 2. Database Keepalive Check:
```bash
curl -i "https://sentrix.yourdomain.com/internal/keepalive?secret=YOUR_KEEPALIVE_SECRET"
```
Expected response:
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-10-30T10:00:00.000000Z"
}
```

### 3. AWS Kinesis Integration Status:
```bash
curl -i https://sentrix.yourdomain.com/api/v1/integrations/aws/kinesis/status \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

---

## 13. Backup & Restoration Procedures

### Automated Daily PostgreSQL Backup:
Create `/opt/sentrix/scripts/backup_db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/sentrix"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

pg_dump -U sentrix_user -h localhost sentrix_db | gzip > "$BACKUP_DIR/sentrix_$TIMESTAMP.sql.gz"

# Retain backups for 14 days
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +14 -delete
```
Make executable and schedule in crontab:
```bash
chmod +x /opt/sentrix/scripts/backup_db.sh
crontab -e
# Add: 0 2 * * * /opt/sentrix/scripts/backup_db.sh
```

### Restoration Procedure:
```bash
gunzip -c /var/backups/sentrix/sentrix_YYYYMMDD_HHMMSS.sql.gz | psql -U sentrix_user -h localhost sentrix_db
```

---

## 14. Zero-Downtime Application Update Procedure

To update SENTRIX with zero downtime:

```bash
cd /opt/sentrix/app

# 1. Pull latest verified release
git fetch --all --tags
git checkout tags/v1.0.0

# 2. Run new database migrations (forward-compatible)
alembic -c backend/alembic.ini upgrade head

# 3. Build updated images
docker compose build

# 4. Perform rolling container recreation
docker compose up -d --no-deps backend
docker compose up -d --no-deps frontend
docker compose up -d --no-deps kinesis-worker

# 5. Clean stale images
docker image prune -f
```

---

## 15. Rollback Procedure

If an issue arises after deployment:

1. **Roll Back Application Code:**
   ```bash
   git checkout tags/v0.9.9
   docker compose up -d --build
   ```

2. **Roll Back Database Schema (if necessary):**
   ```bash
   alembic -c backend/alembic.ini downgrade -1
   ```

3. **Verify System Health:**
   ```bash
   curl -f http://localhost:8000/api/v1/health
   ```

