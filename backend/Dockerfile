# ==============================================================================
# Multi-Stage Production Dockerfile for SENTRIX Backend (FastAPI)
# Security Hardened: Non-Root User, Minimal Slim Base, Isolated Virtualenv
# ==============================================================================

# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/alembic.ini ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir .

# Stage 2: Runtime Production Image
FROM python:3.11-slim AS runner

# Security hardening: Create non-root system group & user
RUN groupadd -g 10001 sentrix && \
    useradd -u 10001 -g sentrix -s /bin/bash -m sentrix

WORKDIR /app

# Install runtime dependencies (e.g. libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy backend source code and migrations
COPY --chown=sentrix:sentrix backend/app /app/app
COPY --chown=sentrix:sentrix backend/alembic.ini /app/alembic.ini
COPY --chown=sentrix:sentrix data/ /app/data/

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    APP_ENV=production \
    DATABASE_URL="sqlite:///./data/sentrix.db"

# Mount persistent data directory owned by non-root user
RUN mkdir -p /app/data && chown -R sentrix:sentrix /app/data

USER sentrix

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# State is currently process-local. Keep one worker until shared state is moved
# to external storage so telemetry, rules, and emergency state stay consistent.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]

