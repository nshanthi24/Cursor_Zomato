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

# data/ may only contain .gitkeep; start.sh builds the catalog when parquet is missing.
COPY data ./data

EXPOSE 8000

CMD ["./scripts/start.sh"]
