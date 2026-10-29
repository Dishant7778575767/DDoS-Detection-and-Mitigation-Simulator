# SENTRIX Deployment & Controlled Evaluation Guide

This guide describes how to run SENTRIX for development, staging, and controlled evaluation. SENTRIX is an intelligent DDoS detection and defensive mitigation platform: it ingests real-time edge telemetry (AWS CloudFront real-time logs via Amazon Kinesis Data Streams), evaluates statistical EWMA baselines and ML inference, and exports reviewable mitigation configurations for AWS WAFv2, Nginx, and Caddy. Edge mitigations require explicit operator review and deployment to AWS WAFv2.

---

## 1. Architecture Overview

Current application components:
- **Frontend:** Next.js 16 standalone web application (Port 3000) providing the SOC Command Center, Live Telemetry Stream, Threat Center, Defense Shield, and Cyber Range simulator.
- **Backend:** FastAPI high-performance asynchronous API (Port 8000) providing:
  - AWS CloudFront Real-Time Log ingestion via Amazon Kinesis Data Streams (`kinesis_consumer`)
  - Real-time HTTP log & request ingestion (`/api/v1/telemetry/ingress` and `/api/v1/integrations/aws/kinesis/mock-ingest`)
  - Adaptive EWMA baseline & Z-score velocity detection (`/api/v1/detection/live`)
  - Random Forest ML classifier (trained on CIC-DDoS2019 dataset)
  - Defensive mitigation state machine with staged Dry-Run rules (`/api/v1/mitigations/defensive`)
  - Configuration snippet exporters for AWS WAFv2, Nginx, and Caddy
  - Discrete-event chaos simulator (`/api/v1/simulations`)
- **Worker:** Dedicated standalone Kinesis streaming worker (`python -m app.workers.kinesis_worker`) consuming CloudFront real-time logs asynchronously without blocking API request threads.

---

## 2. Quickstart with Docker Compose (Recommended)

### Prerequisites:
- Docker Engine $\ge 24.0$
- Docker Compose $\ge 2.20$

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/your-org/DDoS-Detection-and-Mitigation-Simulator.git
cd DDoS-Detection-and-Mitigation-Simulator

# Copy environment template
cp .env.example .env

# Generate a strong API token; Compose refuses to start without it
openssl rand -hex 16
```
Edit `.env` and configure `API_AUTH_TOKEN`. If connecting to AWS Kinesis, set `AWS_REGION=us-east-1` and `AWS_KINESIS_STREAM_NAME=sentrix-cloudfront-realtime-logs`.

### Step 2: Launch SENTRIX Core Services
```bash
docker compose up -d --build
```

### Step 3: (Optional) Launch Dedicated Kinesis Worker Container
```bash
docker compose --profile aws-worker up -d
```

### Step 4: Verify Health & Deployment
```bash
# Check Backend Health
curl -s http://localhost:8000/api/v1/health -H "Authorization: Bearer <YOUR_API_TOKEN>"

# Check Kinesis Integration Status
curl -s http://localhost:8000/api/v1/integrations/aws/kinesis/status -H "Authorization: Bearer <YOUR_API_TOKEN>"
```

Access the SOC Command Center at `http://localhost:3000`.

---

## 3. Local Development Quickstart (Without Docker)

### Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\activate
pip install -e .
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 4. AWS CloudFront & Amazon Kinesis Data Streams Integration

SENTRIX integrates natively with AWS CloudFront Real-Time Access Logs and Amazon Kinesis Data Streams.

### Target Architecture:
```text
Internet ──► AWS CloudFront CDN / AWS Shield Standard / AWS WAFv2 ──► Protected Origin
                  │ (Real-Time Access Logs)
                  ▼
         Amazon Kinesis Data Streams (sentrix-cloudfront-realtime-logs)
                  │
                  ▼
         SENTRIX Dedicated Kinesis Worker (Asynchronous Polling Service)
                  │
                  ▼ (Tab-Delimited Normalization, TTFB conversion, Dedup & Checkpointing)
         Normalized Telemetry (RequestTelemetryItem)
                  │
                  ▼
         Sliding-Window Aggregator ──► Adaptive EWMA & Random Forest Classifier
                                                     │
                                                     ▼
                                          Proposed Defensive Rule
                                                     │ (Operator Approval)
                                                     ▼
                                          AWS WAFv2 Export (CLOUDFRONT Scope, us-east-1)
```

### Key Architectural Differences from Standard CloudFront Logs:
1. **Real-Time vs Standard Logs:** Standard CloudFront access logs are delivered to Amazon S3 in multi-minute batches (often 5–20 minutes delay), which is unacceptable for real-time DDoS mitigation. CloudFront Real-Time Logs stream events within seconds directly into Amazon Kinesis Data Streams.
2. **Kinesis Polling vs Arbitrary HTTP Push:** CloudFront does not push logs via arbitrary HTTP POST endpoints. Telemetry is streamed into a Kinesis Data Stream and consumed by a dedicated SENTRIX background worker (`app.workers.kinesis_worker`).
3. **Data Format & Field Mapping:** CloudFront real-time logs are tab-delimited (`\t`) records with a configurable field ordering defined in `backend/app/ingestion/cloudfront_parser.py` (`DEFAULT_CLOUDFRONT_LOG_FIELDS`).
4. **Unit Conversion:** `time-to-first-byte` in CloudFront logs is emitted in floating-point seconds (e.g. `0.045` s); SENTRIX converts this to milliseconds (`45.0` ms) for unified pipeline metrics.
5. **Deduplication & Privacy:** CloudFront's `x-edge-request-id` serves as the unique deduplication key persisted in `cloudfront_kinesis_events`. Query parameters (`cs-uri-query`) and cookies (`cs-cookie`) are stripped from normalized URIs to preserve user privacy.

### Step-by-Step AWS Setup Guide:

#### Step 1: Create Amazon Kinesis Data Stream
```bash
aws kinesis create-stream \
    --stream-name sentrix-cloudfront-realtime-logs \
    --shard-count 1 \
    --region us-east-1
```

#### Step 2: Create IAM Role for CloudFront Real-Time Logging
Create an IAM role allowing CloudFront service principal (`cloudfront.amazonaws.com`) to write records into your stream:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "kinesis:DescribeStreamSummary",
                "kinesis:DescribeStream",
                "kinesis:PutRecord",
                "kinesis:PutRecords"
            ],
            "Resource": "arn:aws:kinesis:us-east-1:<ACCOUNT_ID>:stream/sentrix-cloudfront-realtime-logs"
        }
    ]
}
```

#### Step 3: Create CloudFront Real-Time Log Configuration
Configure the log fields matching SENTRIX's standard field set:
```bash
aws cloudfront create-realtime-log-config \
    --name sentrix-realtime-logs \
    --sampling-rate 100 \
    --fields "timestamp" "c-ip" "time-to-first-byte" "sc-status" "sc-bytes" "cs-method" "cs-protocol" "cs-host" "cs-uri-stem" "cs-uri-query" "c-port" "x-edge-location" "x-edge-request-id" "x-host-header" "time-taken" "cs-protocol-version" "c-ip-version" "cs-user-agent" \
    --end-points StreamType=Kinesis,KinesisStreamConfig='{RoleARN=arn:aws:iam::<ACCOUNT_ID>:role/CloudFrontKinesisRole,StreamARN=arn:aws:kinesis:us-east-1:<ACCOUNT_ID>:stream/sentrix-cloudfront-realtime-logs}'
```
Attach this real-time log configuration to your CloudFront distribution's default cache behavior.

#### Step 4: Run the SENTRIX Kinesis Worker
Launch the worker service using standard IAM credentials (via IAM Role on EC2/ECS/EKS or environment credentials):
```bash
python -m app.workers.kinesis_worker
```
The worker will:
- Discover active shards on `sentrix-cloudfront-realtime-logs`
- Resume from persistent sequence number checkpoints in table `kinesis_checkpoints`
- Ingest and deduplicate batches using table `cloudfront_kinesis_events`
- Push items into the active sliding-window telemetry aggregator

---

## 5. AWS WAFv2 Defensive Mitigation & Deployment

SENTRIX generates ready-to-deploy AWS WAFv2 artifacts for approved IP blocks:

> [!IMPORTANT]
> **AWS WAFv2 CloudFront Scope Requirement:**
> AWS requires that all WebACLs and IPSets attached to CloudFront distributions MUST be created in AWS Region `us-east-1` with `--scope CLOUDFRONT`.

### 1. Export Formats Available in SOC Defense Shield (`/mitigation`):
- **AWS WAFv2 JSON:** Complete WebACL Rule definitions and IPSet schema (`GET /api/v1/mitigations/export/aws-waf`).
- **AWS CLI Deployment Script:** Executable bash script (`GET /api/v1/mitigations/export/aws-waf/cli`) that checks if the IPSet exists, queries its lock token, and atomically updates or creates it in `us-east-1`.
- **Nginx Configuration:** Reverse proxy blocklist snippet (`GET /api/v1/mitigations/export/nginx`).
- **Caddy Configuration:** Caddyfile route matcher snippet (`GET /api/v1/mitigations/export/caddy`).

### 2. AWS Shield Standard Coexistence:
- **L3/L4 Volumetric Attacks:** AWS Shield Standard is automatically active at all CloudFront points of presence worldwide and absorbs SYN floods, UDP reflection, and network-layer floods at zero cost.
- **L7 Application Attacks:** SENTRIX detects sophisticated Layer-7 application floods, credential stuffing, and Slowloris connection starvation, proposing surgical IPSet updates for AWS WAFv2.

---

## 6. Security Controls & Best Practices

- **Zero Hardcoded Secrets:** AWS credentials rely on default credential provider chains (IAM instance profiles, ECS task roles, or environment variables). Static keys must never be committed.
- **Data Privacy & GDPR Compliance:** Telemetry normalizer strips query parameters and sensitive headers from URIs before persistence and aggregation.
- **Fail-Closed Safety Gate:** All mitigation rules undergo strict RFC 1918 private network allowlist verification, maximum TTL enforcement (max 300s), and emergency kill-switch checks.
- **Operator-in-the-Loop:** Rules default to `DRY_RUN` mode (which translates to AWS WAF `Count` action) for validation before active `Block` enforcement.
