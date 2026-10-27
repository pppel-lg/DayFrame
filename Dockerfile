# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="Dayframe" \
      org.opencontainers.image.description="Private local selfie journal with portable archives" \
      org.opencontainers.image.source="https://github.com/pppel-lg/DayFrame" \
      org.opencontainers.image.version="1.0.0"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DAYFRAME_DATA=/data \
    DAYFRAME_BACKUPS=/backups \
    FRONTEND_DIST=/app/frontend/dist
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 dayframe \
    && useradd --uid 10001 --gid dayframe --no-create-home dayframe \
    && mkdir -p /data /backups \
    && chown dayframe:dayframe /data /backups
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist/
USER dayframe
EXPOSE 8765 8766
VOLUME ["/data", "/backups"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=4)"
CMD ["python", "-m", "uvicorn", "backend.dayframe.main:app", "--host", "0.0.0.0", "--port", "8765", "--no-access-log"]
