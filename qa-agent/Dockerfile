# Unified QA agent image (SPT + release-gate). ui_evidence stays a sibling package.
ARG BASE_IMAGE=ghcr.io/am-portfolio/am-ui-test-agent-base:latest
FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/qa-agent:/app \
    APP_PORT=8150 \
    QA_AGENT_PORT=8150 \
    QA_AGENT_COLOCATED=1 \
    QA_AGENT_WORKER_ENABLED=1 \
    HEADLESS=true \
    TZ=Asia/Kolkata

COPY pyproject.toml README.md ./
COPY qa-agent qa-agent/
COPY ui_evidence ui_evidence/
COPY qa-portal-ui qa-portal-ui/

RUN pip install --no-cache-dir ".[temporal,pdf,otel]" \
    && (test -x qa-agent/vendor/bin/k6 && cp qa-agent/vendor/bin/k6 /usr/local/bin/k6 || true)

EXPOSE 8150

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -f "http://localhost:${APP_PORT}/health" || exit 1

CMD ["am-qa-agents"]
