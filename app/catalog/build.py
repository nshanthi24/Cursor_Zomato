"""Build or reuse the on-disk catalog snapshot."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from app.catalog.ingest import download_train_split
from app.catalog.preprocess import preprocess
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Bump when the canonical parquet schema changes (for example new columns).
CATALOG_SCHEMA_VERSION = 2


def meta_path_for(catalog_path: Path) -> Path:
    return catalog_path.with_name(f"{catalog_path.stem}.meta.json")


def read_meta(catalog_path: Path) -> dict[str, object] | None:
    path = meta_path_for(catalog_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_meta(catalog_path: Path, settings: Settings, row_count: int) -> None:
    payload = {
        "dataset_id": settings.dataset_id,
        "dataset_revision": settings.dataset_revision,
        "budget_low_max": settings.budget_low_max,
        "budget_medium_max": settings.budget_medium_max,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "row_count": row_count,
    }
    meta_path_for(catalog_path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def snapshot_matches(catalog_path: Path, settings: Settings) -> bool:
    if not catalog_path.is_file():
        return False
    meta = read_meta(catalog_path)
    if meta is None:
        return False
    return (
        meta.get("dataset_id") == settings.dataset_id
        and meta.get("dataset_revision") == settings.dataset_revision
        and meta.get("budget_low_max") == settings.budget_low_max
        and meta.get("budget_medium_max") == settings.budget_medium_max
        and meta.get("schema_version") == CATALOG_SCHEMA_VERSION
    )


def _write_parquet_atomically(frame, catalog_path: Path) -> None:
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=catalog_path.parent,
        suffix=".parquet.tmp",
    ) as handle:
        temp_path = Path(handle.name)
    try:
        frame.to_parquet(temp_path, index=False)
        temp_path.replace(catalog_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


def build_catalog(settings: Settings | None = None) -> Path:
    """Write `data/catalog.parquet` or reuse it when the revision still matches."""
    settings = settings or get_settings()
    catalog_path = Path(settings.catalog_path)

    if snapshot_matches(catalog_path, settings):
        logger.info(
            "Reusing catalog snapshot at %s for revision %s",
            catalog_path,
            settings.dataset_revision,
        )
        return catalog_path.resolve()

    raw = download_train_split(settings.dataset_id, settings.dataset_revision)
    catalog = preprocess(
        raw,
        budget_low_max=settings.budget_low_max,
        budget_medium_max=settings.budget_medium_max,
    )
    _write_parquet_atomically(catalog, catalog_path)
    write_meta(catalog_path, settings, row_count=len(catalog))
    logger.info(
        "Wrote catalog with %s restaurants to %s",
        len(catalog),
        catalog_path,
    )
    return catalog_path.resolve()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    path = build_catalog()
    print(path)


if __name__ == "__main__":
    main()
