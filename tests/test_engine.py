"""Recommendation engine validation, repair, and fallback behavior."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.catalog.preprocess import CANONICAL_COLUMNS
from app.catalog.store import CatalogStore
from app.config import Settings
from app.llm.client import LLMClientError
from app.recommend.engine import FALLBACK_SUMMARY, RecommendationEngine
from app.recommend.filter import FilterRequest
from app.recommend.prompt import build_candidate_card, build_prompt


def _row(
    restaurant_id: str,
    name: str,
    *,
    rating: float,
    votes: int,
    cost: int,
) -> dict[str, object]:
    return {
        "id": restaurant_id,
        "name": name,
        "location": "Banashankari",
        "area": "Banashankari",
        "cuisines": ["chinese", "north indian"],
        "cuisines_display": "Chinese, North Indian",
        "rating": rating,
        "votes": votes,
        "cost_for_two": cost,
        "budget_band": "medium",
        "veg_type": "veg_and_non_veg",
        "rest_type": "Casual Dining",
        "dish_liked": "Noodles",
        "online_order": True,
        "book_table": False,
        "listed_types": ["Delivery"],
        "review_excerpt": "Fast service and good noodles.",
    }


@pytest.fixture
def store() -> CatalogStore:
    rows = [
        _row("id-1", "Alpha", rating=4.5, votes=100, cost=800),
        _row("id-2", "Bravo", rating=4.4, votes=90, cost=750),
        _row("id-3", "Charlie", rating=4.3, votes=80, cost=700),
        _row("id-4", "Delta", rating=4.2, votes=70, cost=650),
        _row("id-5", "Echo", rating=4.1, votes=60, cost=600),
        _row("id-6", "Foxtrot", rating=4.0, votes=50, cost=550),
    ]
    return CatalogStore(pd.DataFrame(rows, columns=CANONICAL_COLUMNS))


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        candidate_limit=15,
        result_limit=5,
        llm_api_key="test-key",
        llm_model="openai/gpt-oss-20b",
        llm_base_url="https://api.groq.com/openai/v1",
    )


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if not self.responses:
            raise LLMClientError("no more fake responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


def _request(**overrides: object) -> FilterRequest:
    payload = {
        "location": "Banashankari",
        "budget": "medium",
        "cuisine": "Chinese",
        "min_rating": 4.0,
        "additional_preferences": None,
    }
    payload.update(overrides)
    return FilterRequest(**payload)  # type: ignore[arg-type]


def test_valid_json_is_reordered_capped_and_uses_catalog_facts(
    store: CatalogStore, settings: Settings
) -> None:
    payload = {
        "summary": "A solid Chinese shortlist.",
        "recommendations": [
            {
                "id": "id-3",
                "rank": 2,
                "explanation": "Second pick, maybe costs 9999.",
            },
            {
                "id": "id-1",
                "rank": 1,
                "explanation": "Top pick.",
            },
            {"id": "id-2", "rank": 3, "explanation": "Third."},
            {"id": "id-4", "rank": 4, "explanation": "Fourth."},
            {"id": "id-5", "rank": 5, "explanation": "Fifth."},
            {"id": "id-6", "rank": 6, "explanation": "Should be truncated."},
        ],
    }
    client = FakeClient([json.dumps(payload)])
    engine = RecommendationEngine(store, settings, client=client)

    result = engine.recommend(_request())

    assert result.used_fallback is False
    assert [item.id for item in result.recommendations] == [
        "id-1",
        "id-3",
        "id-2",
        "id-4",
        "id-5",
    ]
    assert result.recommendations[0].cost_for_two == 800
    assert result.recommendations[0].name == "Alpha"
    assert "9999" in result.recommendations[1].explanation
    assert len(client.calls) == 1


def test_unknown_id_removed_and_duplicate_kept_once(
    store: CatalogStore, settings: Settings
) -> None:
    payload = {
        "summary": "Mixed ids.",
        "recommendations": [
            {"id": "id-1", "rank": 1, "explanation": "First."},
            {"id": "missing", "rank": 2, "explanation": "Fake."},
            {"id": "id-1", "rank": 3, "explanation": "Dup."},
            {"id": "id-2", "rank": 4, "explanation": "Second."},
        ],
    }
    client = FakeClient([json.dumps(payload)])
    result = RecommendationEngine(store, settings, client=client).recommend(_request())

    assert [item.id for item in result.recommendations] == ["id-1", "id-2"]
    assert result.used_fallback is False
    assert result.dropped_ids >= 2


def test_invalid_json_triggers_one_repair_then_fallback(
    store: CatalogStore, settings: Settings
) -> None:
    client = FakeClient(["not-json", "still-not-json"])
    result = RecommendationEngine(store, settings, client=client).recommend(_request())

    assert len(client.calls) == 2
    assert "Invalid reply to repair" in client.calls[1]
    assert result.used_fallback is True
    assert result.summary == FALLBACK_SUMMARY
    assert 1 <= len(result.recommendations) <= 5
    assert all(
        "written recommendation was unavailable" in item.explanation
        for item in result.recommendations
    )


def test_repair_success_after_invalid_json(
    store: CatalogStore, settings: Settings
) -> None:
    good = {
        "summary": "Repaired.",
        "recommendations": [
            {"id": "id-2", "rank": 1, "explanation": "Fixed."},
        ],
    }
    client = FakeClient(["nope", json.dumps(good)])
    result = RecommendationEngine(store, settings, client=client).recommend(_request())

    assert len(client.calls) == 2
    assert result.used_fallback is False
    assert [item.id for item in result.recommendations] == ["id-2"]


def test_client_timeout_uses_fallback(
    store: CatalogStore, settings: Settings
) -> None:
    client = FakeClient(
        [
            LLMClientError("LLM request timed out"),
            LLMClientError("LLM request timed out"),
        ]
    )
    result = RecommendationEngine(store, settings, client=client).recommend(_request())

    assert len(client.calls) == 2
    assert result.used_fallback is True
    assert len(result.recommendations) == 5


def test_zero_candidates_make_no_client_calls(
    store: CatalogStore, settings: Settings
) -> None:
    client = FakeClient([])
    result = RecommendationEngine(store, settings, client=client).recommend(
        _request(location="Not A Place")
    )

    assert client.calls == []
    assert result.recommendations == []
    assert result.candidate_count == 0
    assert result.used_fallback is False
    assert result.empty_reason is not None


def test_json_fence_does_not_consume_repair(
    store: CatalogStore, settings: Settings
) -> None:
    payload = {
        "summary": "Fenced.",
        "recommendations": [
            {"id": "id-1", "rank": 1, "explanation": "Ok."},
        ],
    }
    fenced = f"```json\n{json.dumps(payload)}\n```"
    client = FakeClient([fenced])
    result = RecommendationEngine(store, settings, client=client).recommend(_request())

    assert len(client.calls) == 1
    assert result.used_fallback is False
    assert result.recommendations[0].id == "id-1"


def test_additional_preferences_put_review_excerpt_on_cards(
    store: CatalogStore, settings: Settings
) -> None:
    filtered_request = _request(additional_preferences="quick service")
    prompt = build_prompt(
        filtered_request,
        [store.get("id-1") or {}],
        result_limit=5,
    )
    assert "review_excerpt" in prompt
    card = build_candidate_card(
        store.get("id-1") or {},
        include_review_excerpt=True,
    )
    assert card["review_excerpt"] == "Fast service and good noodles."

    bare_card = build_candidate_card(
        store.get("id-1") or {},
        include_review_excerpt=False,
    )
    assert "review_excerpt" not in bare_card


def test_blank_api_key_uses_fallback_without_crash(
    store: CatalogStore, settings: Settings
) -> None:
    blank = settings.model_copy(update={"llm_api_key": ""})
    engine = RecommendationEngine(store, blank)
    result = engine.recommend(_request())
    assert result.used_fallback is True
    assert len(result.recommendations) == 5
