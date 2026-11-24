#!/usr/bin/env sh
set -eu

CATALOG_PATH="${CATALOG_PATH:-data/catalog.parquet}"

if [ ! -f "$CATALOG_PATH" ]; then
  echo "Catalog missing at ${CATALOG_PATH}; building snapshot (may OOM on small plans)..."
  python -m app.catalog
else
  echo "Using existing catalog at ${CATALOG_PATH}"
fi

PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
