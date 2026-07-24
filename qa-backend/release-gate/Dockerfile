FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY registry ./registry
COPY config ./config
COPY catalog ./catalog

RUN pip install --no-cache-dir ".[temporal]"

ENV QA_AGENT_ENV=prod
ENV TEMPORAL_NAMESPACE=qa-agent
ENV TEMPORAL_TASK_QUEUE=qa-agent-release-v1
EXPOSE 8150

CMD ["am-qa-agent-gateway"]
