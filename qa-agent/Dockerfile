# Unified am-qa-agents — Specs (SPT) + UI evidence (Playwright) + release-gate
# One container / one release name. No separate am-ui-test-agent image.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

ARG K6_VERSION=v0.54.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app/qa-agent:/app/qa-agent/release_gate \
    APP_NAME=am-qa-agents \
    APP_PORT=8150 \
    QA_AGENT_PORT=8150 \
    QA_AGENT_COLOCATED=1 \
    QA_AGENT_WORKER_ENABLED=1 \
    HEADLESS=true \
    TZ=Asia/Kolkata \
    K6_BIN=/usr/local/bin/k6

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && curl -fsSL "https://github.com/grafana/k6/releases/download/${K6_VERSION}/k6-${K6_VERSION}-linux-amd64.tar.gz" \
       | tar -xz -C /tmp \
    && mv "/tmp/k6-${K6_VERSION}-linux-amd64/k6" /usr/local/bin/k6 \
    && chmod +x /usr/local/bin/k6 \
    && k6 version \
    && rm -rf /var/lib/apt/lists/* /tmp/k6-*

COPY pyproject.toml README.md ./
COPY qa-agent qa-agent/
COPY qa-portal-ui qa-portal-ui/

RUN pip install --no-cache-dir ".[temporal,pdf,otel]" tzdata \
    && (test -x qa-agent/vendor/bin/k6 && cp qa-agent/vendor/bin/k6 /usr/local/bin/k6 || true) \
    && test -x /usr/local/bin/k6
# Chromium already present in playwright/python base (UI evidence)

EXPOSE 8150

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -f "http://localhost:${APP_PORT}/health" || exit 1

CMD ["am-qa-agents"]
