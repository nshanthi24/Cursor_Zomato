"""In-memory catalog loaded once from the parquet snapshot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.catalog.build import read_meta, snapshot_matches
from app.config import Settings

logger = logging.getLogger(__name__)


class CatalogStoreError(RuntimeError):
    """Raised when the catalog snapshot cannot be loaded safely."""


class CatalogStore:
    """Serves restaurant lookups and distinct form values from memory."""

    def __init__(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            raise CatalogStoreError("Catalog snapshot is empty")
        self._frame = frame.copy()
        self._by_id: dict[str, dict[str, Any]] = {}
        for row in self._frame.to_dict(orient="records"):
            normalized = dict(row)
            normalized["cuisines"] = _as_str_list(normalized.get("cuisines"))
            normalized["listed_types"] = _as_str_list(normalized.get("listed_types"))
            self._by_id[str(normalized["id"])] = normalized
        self._locations = self._build_locations()
        self._cuisines = self._build_cuisines()
        self._ready = True

    @classmethod
    def load(cls, settings: Settings) -> CatalogStore:
        catalog_path = Path(settings.catalog_path)
        if not catalog_path.is_file():
            raise CatalogStoreError(
                f"Catalog snapshot is missing at {catalog_path}"
            )

        meta = read_meta(catalog_path)
        if meta is None:
            raise CatalogStoreError(
                f"Catalog metadata sidecar is missing or unreadable for {catalog_path}"
            )
        if not snapshot_matches(catalog_path, settings):
            raise CatalogStoreError(
                "Catalog snapshot does not match the configured dataset revision "
                "or budget cutoffs"
            )

        try:
            frame = pd.read_parquet(catalog_path)
        except Exception as exc:  # noqa: BLE001 - surface corrupt snapshots clearly
            raise CatalogStoreError(
                f"Catalog snapshot could not be read from {catalog_path}"
            ) from exc

        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise CatalogStoreError("Catalog snapshot is empty")

        store = cls(frame)
        logger.info(
            "Loaded catalog with %s restaurants from %s",
            len(store),
            catalog_path,
        )
        return store

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def frame(self) -> pd.DataFrame:
        return self._frame

    def __len__(self) -> int:
        return len(self._frame)

    def exists(self, restaurant_id: str) -> bool:
        return restaurant_id in self._by_id

    def get(self, restaurant_id: str) -> dict[str, Any] | None:
        row = self._by_id.get(restaurant_id)
        return None if row is None else dict(row)

    def locations(self) -> list[str]:
        return list(self._locations)

    def cuisines(self) -> list[str]:
        return list(self._cuisines)

    def _build_locations(self) -> list[str]:
        seen: dict[str, str] = {}
        for column in ("location", "area"):
            for value in self._frame[column].tolist():
                text = _clean_label(value)
                if text is None:
                    continue
                key = text.casefold()
                if key not in seen:
                    seen[key] = text
        return sorted(seen.values(), key=str.casefold)

    def _build_cuisines(self) -> list[str]:
        seen: dict[str, str] = {}
        for record in self._frame.to_dict(orient="records"):
            tokens = _as_str_list(record.get("cuisines"))
            display_tokens = [
                part.strip()
                for part in str(record.get("cuisines_display") or "").split(",")
                if part.strip()
            ]
            for index, token in enumerate(tokens):
                normalized = _clean_label(token)
                if normalized is None:
                    continue
                key = normalized.casefold()
                display = (
                    display_tokens[index]
                    if index < len(display_tokens)
                    else normalized
                )
                display = _clean_label(display) or normalized
                if key not in seen:
                    seen[key] = display
        return sorted(seen.values(), key=str.casefold)


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if hasattr(value, "tolist"):
        return _as_str_list(value.tolist())
    return [str(value)]


def _clean_label(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
