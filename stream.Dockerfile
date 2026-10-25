# WebSocket stream service (contract v1.1) for Azure Container Apps.
# The engine has no runtime dependencies, so the image is just Python, the code and the match data.
#
#   docker build -f stream.Dockerfile -t baja-stream .
#   docker run -p 8080:8080 -e STREAM_SPEED=60 baja-stream
FROM python:3.12-slim

WORKDIR /app
COPY src ./src
COPY data ./data

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    STREAM_SPEED=1 \
    STREAM_HALF_TIME_PAUSE=0
EXPOSE 8080
USER nobody
CMD ["sh", "-c", "exec python -m baja_insights serve --data /app/data --host 0.0.0.0 --port $PORT --speed $STREAM_SPEED --half-time-pause $STREAM_HALF_TIME_PAUSE"]
