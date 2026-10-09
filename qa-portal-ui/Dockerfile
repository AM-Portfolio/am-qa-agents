# Static Flutter web portal — independent of am-qa-agents Python image.
# Build context: qa-portal-ui/ (expects build/web already present).
#
#   flutter build web --release --base-href=/qa/ui/ --dart-define=API_BASE=/qa --dart-define=ROOT_PATH=/qa
#   docker build -t ghcr.io/am-portfolio/am-qa-agents/am-qa-portal-ui:local qa-portal-ui

FROM nginx:1.27-alpine

LABEL org.opencontainers.image.source="https://github.com/AM-Portfolio/am-qa-agents"
LABEL org.opencontainers.image.title="am-qa-portal-ui"

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Serve under /qa/ui/ to match --base-href=/qa/ui/
COPY build/web /usr/share/nginx/html/qa/ui

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ || exit 1
