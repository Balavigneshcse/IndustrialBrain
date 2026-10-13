# IndusMind API image. Build from the repository root:  docker compose --profile full build api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UPLOAD_DIR=/data/uploads

WORKDIR /srv
RUN groupadd --system indusmind \
    && useradd --system --gid indusmind --uid 10001 --home-dir /srv indusmind \
    && mkdir -p /data/uploads && chown indusmind:indusmind /data/uploads

COPY server/requirements.txt server/requirements.txt
RUN pip install -r server/requirements.txt

COPY server/ server/
USER indusmind
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=4)"

# Apply migrations, then serve. The app logs each request itself, so uvicorn's access log is off.
CMD ["sh", "-c", "python -m server.app.cli migrate && exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
