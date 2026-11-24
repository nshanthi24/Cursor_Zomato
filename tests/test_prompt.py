"""Candidate card and prompt construction."""

from __future__ import annotations

import json

from app.recommend.filter import FilterRequest
from app.recommend.prompt import build_candidate_card, build_prompt


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "abc",
        "name": 'Cafe "Quote"',
        "location": "Banashankari",
        "cuisines": ["chinese"],
        "cuisines_display": "Chinese",
        "rating": 4.1,
        "votes": 10,
        "cost_for_two": 800,
        "budget_band": "medium",
        "veg_type": "veg_and_non_veg",
        "rest_type": "Cafe",
        "dish_liked": "Noodles\nSoup",
        "online_order": True,
        "book_table": False,
        "listed_types": ["Delivery"],
        "review_excerpt": "Great {place} for lunch.",
    }
    row.update(overrides)
    return row


def test_cards_omit_review_excerpt_without_additional_preferences() -> None:
    card = build_candidate_card(_candidate(), include_review_excerpt=False)
    assert "review_excerpt" not in card
    assert set(card) >= {
        "id",
        "name",
        "location",
        "cuisines",
        "rating",
        "votes",
        "cost_for_two",
        "rest_type",
        "online_order",
        "book_table",
        "dish_liked",
        "listed_types",
    }


def test_prompt_includes_excerpt_only_with_additional_preferences() -> None:
    request = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
        additional_preferences="quick service",
    )
    prompt = build_prompt(request, [_candidate()], result_limit=5)
    payload = json.loads(prompt.split("Candidate payload:\n", 1)[1])
    assert payload["preferences"]["additional_preferences"] == "quick service"
    assert "review_excerpt" in payload["candidates"][0]
    assert payload["candidates"][0]["review_excerpt"] == "Great {place} for lunch."

    bare = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
        additional_preferences="   ",
    )
    bare_prompt = build_prompt(bare, [_candidate()], result_limit=5)
    bare_payload = json.loads(bare_prompt.split("Candidate payload:\n", 1)[1])
    assert bare_payload["preferences"]["additional_preferences"] is None
    assert "review_excerpt" not in bare_payload["candidates"][0]


def test_prompt_serializes_special_characters_as_json() -> None:
    prompt = build_prompt(
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
        ),
        [_candidate()],
        result_limit=5,
    )
    payload = json.loads(prompt.split("Candidate payload:\n", 1)[1])
    assert payload["candidates"][0]["name"] == 'Cafe "Quote"'
    assert "url" not in payload["candidates"][0]
