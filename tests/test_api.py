"""HTTP API contracts for meta and recommendations."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.catalog.preprocess import CANONICAL_COLUMNS
from app.catalog.store import CatalogStore
from app.config import Settings
from app.main import create_app
from app.recommend.engine import EngineResult
from app.recommend.validate import ValidatedRecommendation


def _store() -> CatalogStore:
    frame = pd.DataFrame(
        [
            {
                "id": "id-1",
                "name": "Jalsa",
                "location": "Banashankari",
                "area": "Banashankari",
                "cuisines": ["chinese", "north indian"],
                "cuisines_display": "Chinese, North Indian",
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
            }
        ],
        columns=CANONICAL_COLUMNS,
    )
    return CatalogStore(frame)


class FakeEngine:
    def __init__(self, result: EngineResult) -> None:
        self.result = result
        self.calls = 0
        self.last_request = None

    def recommend(self, request):  # noqa: ANN001
        self.calls += 1
        self.last_request = request
        return self.result


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, additional_preferences_max=500)


def test_meta_shape_matches_architecture(settings: Settings) -> None:
    with TestClient(create_app(settings=settings, store=_store())) as client:
        response = client.get("/api/meta")
        assert response.status_code == 200
        body = response.json()
        assert body["locations"] == ["Banashankari"]
        assert body["cuisines"] == ["Chinese", "North Indian"]
        assert body["budget_bands"] == ["low", "medium", "high"]
        assert body["veg_types"] == ["any", "pure_veg", "veg_and_non_veg"]
        assert body["rating_min"] == 0
        assert body["rating_max"] == 5
        assert body["budget_low_max"] == settings.budget_low_max
        assert body["budget_medium_max"] == settings.budget_medium_max


def test_valid_body_returns_engine_payload(settings: Settings) -> None:
    engine = FakeEngine(
        EngineResult(
            summary="A shortlist.",
            recommendations=[
                ValidatedRecommendation(
                    id="id-1",
                    name="Jalsa",
                    cuisines="Chinese, North Indian",
                    rating=4.1,
                    cost_for_two=800,
                    budget_band="medium",
                    veg_type="veg_and_non_veg",
                    location="Banashankari",
                    explanation="Fits the filters.",
                )
            ],
            candidate_count=3,
            used_fallback=False,
        )
    )
    with TestClient(
        create_app(settings=settings, store=_store(), engine=engine)
    ) as client:
        response = client.post(
            "/api/recommendations",
            json={
                "location": "banashankari",
                "budget": "MEDIUM",
                "cuisine": "chinese",
                "min_rating": 4.0,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"] == "A shortlist."
        assert len(body["recommendations"]) == 1
        assert body["meta"]["candidate_count"] == 3
        assert body["meta"]["used_fallback"] is False
        assert engine.calls == 1
        assert engine.last_request.location == "Banashankari"
        assert engine.last_request.budget == "medium"
        assert engine.last_request.cuisine == "Chinese"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"budget": "medium", "cuisine": "Chinese", "min_rating": 4},
        {
            "location": "Not A Place",
            "budget": "medium",
            "cuisine": "Chinese",
            "min_rating": 4,
        },
        {
            "location": "Banashankari",
            "budget": "medium",
            "cuisine": "Martian",
            "min_rating": 4,
        },
        {
            "location": "Banashankari",
            "budget": "cheap",
            "cuisine": "Chinese",
            "min_rating": 4,
        },
        {
            "location": "Banashankari",
            "budget": "medium",
            "cuisine": "Chinese",
            "min_rating": 6,
        },
    ],
)
def test_invalid_requests_return_400_without_engine(
    settings: Settings, payload: dict
) -> None:
    engine = FakeEngine(
        EngineResult(
            summary="should not run",
            recommendations=[],
            candidate_count=0,
            used_fallback=False,
        )
    )
    with TestClient(
        create_app(settings=settings, store=_store(), engine=engine)
    ) as client:
        response = client.post("/api/recommendations", json=payload)
        assert response.status_code == 400
        assert engine.calls == 0


def test_store_not_ready_returns_503(settings: Settings) -> None:
    not_ready = SimpleNamespace(ready=False)
    with TestClient(
        create_app(settings=settings, store=not_ready)  # type: ignore[arg-type]
    ) as client:
        assert client.get("/api/meta").status_code == 503
        assert (
            client.post(
                "/api/recommendations",
                json={
                    "location": "Banashankari",
                    "budget": "medium",
                    "cuisine": "Chinese",
                    "min_rating": 4,
                },
            ).status_code
            == 503
        )


def test_empty_engine_result_includes_reason(settings: Settings) -> None:
    engine = FakeEngine(
        EngineResult(
            summary="No restaurants matched these filters.",
            recommendations=[],
            candidate_count=0,
            used_fallback=False,
            empty_reason="No rows matched location, cuisine, budget, and minimum rating.",
        )
    )
    with TestClient(
        create_app(settings=settings, store=_store(), engine=engine)
    ) as client:
        response = client.post(
            "/api/recommendations",
            json={
                "location": "Banashankari",
                "budget": "medium",
                "cuisine": "Chinese",
                "min_rating": 4.0,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["recommendations"] == []
        assert body["meta"]["candidate_count"] == 0
        assert body["meta"]["used_fallback"] is False
        assert "matched" in body["meta"]["empty_reason"]


def test_fallback_engine_result(settings: Settings) -> None:
    engine = FakeEngine(
        EngineResult(
            summary="Fallback summary.",
            recommendations=[
                ValidatedRecommendation(
                    id="id-1",
                    name="Jalsa",
                    cuisines="Chinese, North Indian",
                    rating=4.1,
                    cost_for_two=800,
                    budget_band="medium",
                    veg_type="veg_and_non_veg",
                    location="Banashankari",
                    explanation="Ordered by rating and votes.",
                )
            ],
            candidate_count=4,
            used_fallback=True,
        )
    )
    with TestClient(
        create_app(settings=settings, store=_store(), engine=engine)
    ) as client:
        response = client.post(
            "/api/recommendations",
            json={
                "location": "Banashankari",
                "budget": "medium",
                "cuisine": "Chinese",
                "min_rating": 4.0,
            },
        )
        assert response.status_code == 200
        assert response.json()["meta"]["used_fallback"] is True


def test_additional_preferences_over_cap_returns_400(settings: Settings) -> None:
    engine = FakeEngine(
        EngineResult(
            summary="unused",
            recommendations=[],
            candidate_count=0,
            used_fallback=False,
        )
    )
    with TestClient(
        create_app(settings=settings, store=_store(), engine=engine)
    ) as client:
        response = client.post(
            "/api/recommendations",
            json={
                "location": "Banashankari",
                "budget": "medium",
                "cuisine": "Chinese",
                "min_rating": 4.0,
                "additional_preferences": "x" * 501,
            },
        )
        assert response.status_code == 400
        assert engine.calls == 0


def test_get_recommendations_not_allowed(settings: Settings) -> None:
    with TestClient(create_app(settings=settings, store=_store())) as client:
        assert client.get("/api/recommendations").status_code == 405


def test_home_page_renders(settings: Settings) -> None:
    with TestClient(create_app(settings=settings, store=_store())) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Thindi" in response.text
        assert "./app.js" in response.text
        assert "Low (≤ ₹500)" in response.text
        assert "Find restaurants" in response.text
        assert "Veg preference" in response.text


def test_cors_headers_for_configured_origin(settings: Settings) -> None:
    settings = settings.model_copy(
        update={"cors_origins": "https://thindi.vercel.app,http://localhost:3000"}
    )
    with TestClient(create_app(settings=settings, store=_store())) as client:
        response = client.options(
            "/api/meta",
            headers={
                "Origin": "https://thindi.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://thindi.vercel.app"
        )
