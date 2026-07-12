# ── Stage 1: frontend build ─────────────────────────────────────────────────
FROM node:22-alpine AS web
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# ── Stage 2: runtime ────────────────────────────────────────────────────────
# python slim + a single ~30 MB typst binary replaces the old ~3 GB texlive
# image; cold starts drop from tens of seconds to a few.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

ARG TYPST_VERSION=0.14.2
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xz-utils ca-certificates \
    && curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
       | tar -xJ --strip-components=1 -C /usr/local/bin "typst-x86_64-unknown-linux-musl/typst" \
    && typst --version \
    && apt-get purge -y curl xz-utils \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY templates/ templates/
COPY --from=web /build/dist frontend/dist

# Non-root user; needs write access to /app for sqlite db
RUN useradd --create-home appuser \
    && mkdir -p templates/.compile \
    && chown -R appuser:appuser /app
USER appuser

ENV ENV=prod \
    PORT=8080 \
    TYPST_BIN=/usr/local/bin/typst

EXPOSE 8080
# --proxy-headers + trusting the Cloud Run front proxy lets the app see the real
# https scheme (X-Forwarded-Proto), so the same-origin check in main.py works
# behind TLS termination instead of 403-ing "Origin not allowed".
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips=*"]
