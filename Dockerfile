FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps (build essentials for any wheels if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy source and migration tooling needed at runtime
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# Entrypoint runs migrations then starts the API
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080

CMD ["/usr/local/bin/docker-entrypoint.sh"]
