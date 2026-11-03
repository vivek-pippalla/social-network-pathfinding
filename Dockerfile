ARG PYTHON_IMAGE=python:3.11.14-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder

WORKDIR /build
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEB_CONCURRENCY=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1,::1

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --create-home appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY requirements.txt ./requirements.txt

RUN chown -R appuser:appuser /app
USER 10001:10001

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:5000/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers \"${WEB_CONCURRENCY:-2}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1,::1}\""]
