FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf_cache

WORKDIR /app

# Fresh CA bundle for TLS verification against sites with newer chains
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch first (much smaller than the default CUDA build)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Headless Chromium for JS-rendered pages. Set INSTALL_PLAYWRIGHT=false to
# build a slimmer image for hosts where PLAYWRIGHT_ENABLED=false anyway.
ARG INSTALL_PLAYWRIGHT=true
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
      playwright install --with-deps chromium; \
    fi

COPY . .

# Retry migrations while the DB comes up (local compose profile), then start.
CMD ["sh", "-c", "for i in $(seq 1 30); do alembic upgrade head && break || sleep 2; done && python -m app.main"]
