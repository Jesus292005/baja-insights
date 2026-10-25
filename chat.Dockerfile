# "Ask the match" chat service (POST /api/ask, contracts/chat.schema.json) for Azure Container Apps.
# It needs the agents, the engine, the match data, the contracts and the tool definitions in mocks/.
# Authentication is the container's managed identity (DefaultAzureCredential), so no keys go in the image.
#
#   docker build -f chat.Dockerfile -t baja-chat .
#   docker run -p 8080:8080 -e FOUNDRY_PROJECT_ENDPOINT=... -e FOUNDRY_MODEL=... baja-chat
FROM python:3.12-slim

WORKDIR /app
COPY agents/requirements.txt agents/requirements.txt
RUN pip install --no-cache-dir -r agents/requirements.txt

COPY src ./src
COPY data ./data
COPY mocks ./mocks
COPY contracts ./contracts
COPY agents/baja_agents ./agents/baja_agents

ENV PYTHONPATH=/app/src:/app/agents \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    CHAT_CACHE_DIR=/tmp/ask-cache
EXPOSE 8080
USER nobody
CMD ["python", "-m", "baja_agents", "serve"]
