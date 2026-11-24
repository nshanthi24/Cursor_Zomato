#!/usr/bin/env sh
set -eu

CATALOG_PATH="${CATALOG_PATH:-data/catalog.parquet}"

if [ ! -f "$CATALOG_PATH" ]; then
  echo "Catalog missing at ${CATALOG_PATH}; building snapshot..."
  python -m app.catalog
fi

PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
