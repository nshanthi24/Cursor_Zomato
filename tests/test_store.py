"""In-memory catalog store lookups and metadata lists."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.catalog.build import CATALOG_SCHEMA_VERSION
from app.catalog.preprocess import CANONICAL_COLUMNS
from app.catalog.store import CatalogStore, CatalogStoreError
from app.config import Settings


def _settings(catalog: Path, revision: str = "rev-a") -> Settings:
    return Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_id="example/dataset",
        dataset_revision=revision,
        budget_low_max=500,
        budget_medium_max=1500,
    )


def _write_fixture(catalog: Path, rows: list[dict[str, object]], settings: Settings) -> None:
    frame = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    catalog.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(catalog, index=False)
    meta = {
        "dataset_id": settings.dataset_id,
        "dataset_revision": settings.dataset_revision,
        "budget_low_max": settings.budget_low_max,
        "budget_medium_max": settings.budget_medium_max,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "row_count": len(frame),
    }
    catalog.with_name(f"{catalog.stem}.meta.json").write_text(
        json.dumps(meta),
        encoding="utf-8",
    )


@pytest.fixture
def fixture_catalog(tmp_path: Path) -> tuple[Path, Settings, str]:
    catalog = tmp_path / "catalog.parquet"
    settings = _settings(catalog)
    restaurant_id = "abc123"
    _write_fixture(
        catalog,
        [
            {
                "id": restaurant_id,
                "name": "Jalsa",
                "location": "Banashankari",
                "area": "BTM",
                "cuisines": ["north indian", "chinese"],
                "cuisines_display": "North Indian, Chinese",
                "rating": 4.1,
                "votes": 775,
                "cost_for_two": 800,
                "budget_band": "medium",
                "veg_type": "veg_and_non_veg",
                "rest_type": "Casual Dining",
                "dish_liked": "Pasta",
                "online_order": True,
                "book_table": True,
                "listed_types": ["Buffet"],
                "review_excerpt": "Nice place.",
            },
            {
                "id": "def456",
                "name": "Other Spot",
                "location": "BTM",
                "area": "Banashankari",
                "cuisines": ["chinese", "italian"],
                "cuisines_display": "Chinese, Italian",
                "rating": 4.0,
                "votes": 10,
                "cost_for_two": 600,
                "budget_band": "medium",
                "veg_type": "veg_and_non_veg",
                "rest_type": "Cafe",
                "dish_liked": "",
                "online_order": False,
                "book_table": False,
                "listed_types": ["Delivery"],
                "review_excerpt": "",
            },
            {
                "id": "ghi789",
                "name": "No Place Labels",
                "location": "",
                "area": "",
                "cuisines": ["north indian"],
                "cuisines_display": "north indian",
                "rating": None,
                "votes": 0,
                "cost_for_two": None,
                "budget_band": None,
                "veg_type": "veg_and_non_veg",
                "rest_type": "",
                "dish_liked": "",
                "online_order": False,
                "book_table": False,
                "listed_types": [],
                "review_excerpt": "",
            },
        ],
        settings,
    )
    return catalog, settings, restaurant_id


def test_load_fixture_and_lookup_by_id(
    fixture_catalog: tuple[Path, Settings, str],
) -> None:
    catalog, settings, restaurant_id = fixture_catalog
    store = CatalogStore.load(settings)

    assert store.ready is True
    assert len(store) == 3
    assert store.exists(restaurant_id) is True
    row = store.get(restaurant_id)
    assert row is not None
    assert row["name"] == "Jalsa"
    assert row["location"] == "Banashankari"
    assert row["rating"] == 4.1
    assert store.get("missing") is None
    assert store.exists("missing") is False


def test_locations_and_cuisines_are_sorted_and_deduped(
    fixture_catalog: tuple[Path, Settings, str],
) -> None:
    _, settings, _ = fixture_catalog
    store = CatalogStore.load(settings)

    assert store.locations() == ["Banashankari", "BTM"]
    assert store.cuisines() == ["Chinese", "Italian", "North Indian"]


def test_missing_snapshot_raises(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "missing.parquet")
    with pytest.raises(CatalogStoreError, match="missing"):
        CatalogStore.load(settings)


def test_revision_mismatch_raises(
    fixture_catalog: tuple[Path, Settings, str],
) -> None:
    catalog, settings, _ = fixture_catalog
    bad = _settings(catalog, revision="other-rev")
    with pytest.raises(CatalogStoreError, match="revision"):
        CatalogStore.load(bad)


def test_missing_sidecar_raises(
    fixture_catalog: tuple[Path, Settings, str],
) -> None:
    catalog, settings, _ = fixture_catalog
    catalog.with_name(f"{catalog.stem}.meta.json").unlink()
    with pytest.raises(CatalogStoreError, match="revision|sidecar|metadata"):
        CatalogStore.load(settings)


def test_budget_cutoff_mismatch_raises(
    fixture_catalog: tuple[Path, Settings, str],
) -> None:
    catalog, settings, _ = fixture_catalog
    bad = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_id=settings.dataset_id,
        dataset_revision=settings.dataset_revision,
        budget_low_max=400,
        budget_medium_max=1500,
    )
    with pytest.raises(CatalogStoreError, match="budget|snapshot|match"):
        CatalogStore.load(bad)


def test_empty_catalog_raises(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.parquet"
    settings = _settings(catalog)
    _write_fixture(catalog, [], settings)
    with pytest.raises(CatalogStoreError, match="empty"):
        CatalogStore.load(settings)
