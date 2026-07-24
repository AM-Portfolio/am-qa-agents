# Build from monorepo root:
#   docker build -f qa-backend/api-load/Dockerfile .
# CI (central-build): working_directory=qa-backend/api-load, build_context=../..
#
# Flutter SPA (optional): build web first, then use Dockerfile.flutter-artifact
# or set SPT_PORTAL_FLUTTER=true with SPT_PORTAL_FLUTTER_DIR pointing at build/web.

FROM python:3.12-slim

WORKDIR /app

COPY qa-backend/api-load/requirements.txt .
COPY qa-backend/api-load/vendor/wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

COPY qa-backend/api-load/vendor/bin/k6 /usr/local/bin/k6
RUN chmod +x /usr/local/bin/k6 || true

COPY qa-backend/api-load/app/ app/
COPY qa-backend/api-load/catalog/ catalog/
COPY qa-backend/api-load/k6/ k6/
COPY qa-backend/api-load/playwright/ playwright/
COPY qa-portal-ui /portal-ui

ENV APP_PORT=8150
ENV K6_BIN=/usr/local/bin/k6
ENV DATA_DIR=/data
ENV ROOT_PATH=/spt-poc
ENV SPT_PORTAL_UI_DIR=/portal-ui
ENV PYTHONUNBUFFERED=1
# Default: HTML portal. Enable Flutter when /portal-flutter or build/web is present:
# ENV SPT_PORTAL_FLUTTER=true
# ENV SPT_PORTAL_FLUTTER_DIR=/portal-flutter

EXPOSE 8150

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8150/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT}"]
