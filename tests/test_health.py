"""Health check stays available alongside recommendation routes."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.catalog.preprocess import CANONICAL_COLUMNS
from app.catalog.store import CatalogStore
from app.config import Settings
from app.main import create_app


def _tiny_store() -> CatalogStore:
    frame = pd.DataFrame(
        [
            {
                "id": "abc",
                "name": "Test",
                "location": "Banashankari",
                "area": "Banashankari",
                "cuisines": ["chinese"],
                "cuisines_display": "Chinese",
                "rating": 4.0,
                "votes": 1,
                "cost_for_two": 500,
                "budget_band": "low",
                "veg_type": "veg_and_non_veg",
                "rest_type": "Cafe",
                "dish_liked": "",
                "online_order": False,
                "book_table": False,
                "listed_types": ["Delivery"],
                "review_excerpt": "",
            }
        ],
        columns=CANONICAL_COLUMNS,
    )
    return CatalogStore(frame)


def test_health_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "super-secret-key")
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings=settings, store=_tiny_store())) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "super-secret-key" not in response.text


def test_recommendation_routes_are_mounted() -> None:
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings=settings, store=_tiny_store())) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/health" in paths
        assert "/api/meta" in paths
        assert "/api/recommendations" in paths
        assert client.get("/api/meta").status_code == 200


def test_health_ok_even_when_checking_routes() -> None:
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings=settings, store=_tiny_store())) as client:
        assert client.get("/health").status_code == 200
