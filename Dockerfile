# Multi-stage Dockerfile para despliegue en la nube (Koyeb, Render, Fly, VPS)
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runner

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --group appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

# Asegurar permisos para SQLite y logs
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENV PORT=8000 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "src.main"]
