# ══════════════════════════════════════════════════════════════════════
# VizGenie - Production Dockerfile
# Python 3.12 slim base
# ══════════════════════════════════════════════════════════════════════

FROM python:3.12-slim AS base

# ── System deps ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential      \
        curl                 \
        libpq-dev            \
        git                  \
    && apt-get clean         \
    && rm -rf /var/lib/apt/lists/*

# ── Python env ────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1        \
    PIP_NO_CACHE_DIR=1        \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Install deps first (layer cache) ─────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# ── Copy source ───────────────────────────────────────────────────────
COPY . .

# ── Create runtime directories ────────────────────────────────────────
RUN mkdir -p logs data config metadata chroma_db

# ── Non-root user ─────────────────────────────────────────────────────
RUN addgroup --system vizgenie \
 && adduser  --system --ingroup vizgenie vizgenie \
 && chown -R vizgenie:vizgenie /app

USER vizgenie

# ── Expose Streamlit port ─────────────────────────────────────────────
EXPOSE 8501

# ── Health check ──────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────
ENTRYPOINT ["streamlit", "run", "main.py", \
            "--server.port=8501",           \
            "--server.address=0.0.0.0",     \
            "--server.headless=true",       \
            "--browser.gatherUsageStats=false"]