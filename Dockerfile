FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
COPY frontend ./frontend

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x scripts/start.sh

# Prefer a prebuilt catalog.parquet in the image (avoids OOM on free-tier boot).
COPY data ./data

EXPOSE 8000

CMD ["./scripts/start.sh"]
