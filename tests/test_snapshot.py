"""Catalog snapshot write, reuse, and metadata checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.catalog.build import build_catalog, meta_path_for
from app.catalog.preprocess import CANONICAL_COLUMNS, preprocess
from app.config import Settings


def _raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "url": "http://example",
                "address": "942, 21st Main Road",
                "name": "Jalsa",
                "online_order": "Yes",
                "book_table": "Yes",
                "rate": "4.1/5",
                "votes": 775,
                "phone": "000",
                "location": "Banashankari",
                "rest_type": "Casual Dining",
                "dish_liked": "Pasta",
                "cuisines": "North Indian, Mughlai, Chinese",
                "approx_cost(for two people)": "800",
                "reviews_list": "[('Rated 4.0', 'RATED\\n Nice place.')]",
                "menu_item": "[]",
                "listed_in(type)": "Buffet",
                "listed_in(city)": "Banashankari",
            }
        ]
    )


def test_written_parquet_has_canonical_columns_only(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.parquet"
    frame = preprocess(_raw_frame(), budget_low_max=500, budget_medium_max=1500)
    frame.to_parquet(catalog, index=False)

    loaded = pd.read_parquet(catalog)
    assert list(loaded.columns) == list(CANONICAL_COLUMNS)
    assert "reviews_list" not in loaded.columns
    assert "url" not in loaded.columns
    assert "phone" not in loaded.columns
    assert "menu_item" not in loaded.columns


def test_build_reuses_snapshot_without_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.parquet"
    settings = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-a",
        budget_low_max=500,
        budget_medium_max=1500,
    )

    download = MagicMock(return_value=_raw_frame())
    monkeypatch.setattr("app.catalog.build.download_train_split", download)

    first = build_catalog(settings)
    second = build_catalog(settings)

    assert first == catalog.resolve()
    assert second == catalog.resolve()
    assert download.call_count == 1
    assert meta_path_for(catalog).is_file()

    loaded = pd.read_parquet(catalog)
    assert "reviews_list" not in loaded.columns
    assert len(loaded) == 1


def test_build_redownloads_when_revision_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.parquet"
    settings_a = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-a",
        budget_low_max=500,
        budget_medium_max=1500,
    )
    settings_b = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-b",
        budget_low_max=500,
        budget_medium_max=1500,
    )

    download = MagicMock(return_value=_raw_frame())
    monkeypatch.setattr("app.catalog.build.download_train_split", download)

    build_catalog(settings_a)
    build_catalog(settings_b)
    assert download.call_count == 2


def test_build_redownloads_when_budget_cutoffs_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.parquet"
    settings_a = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-a",
        budget_low_max=500,
        budget_medium_max=1500,
    )
    settings_b = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-a",
        budget_low_max=400,
        budget_medium_max=1500,
    )

    download = MagicMock(return_value=_raw_frame())
    monkeypatch.setattr("app.catalog.build.download_train_split", download)

    build_catalog(settings_a)
    build_catalog(settings_b)
    assert download.call_count == 2


def test_missing_sidecar_forces_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.parquet"
    settings = Settings(
        _env_file=None,
        catalog_path=str(catalog),
        dataset_revision="rev-a",
        budget_low_max=500,
        budget_medium_max=1500,
    )

    download = MagicMock(return_value=_raw_frame())
    monkeypatch.setattr("app.catalog.build.download_train_split", download)

    build_catalog(settings)
    meta_path_for(catalog).unlink()
    build_catalog(settings)
    assert download.call_count == 2
