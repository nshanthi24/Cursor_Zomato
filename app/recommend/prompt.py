"""Prompt and candidate-card construction."""

from __future__ import annotations

import json
from typing import Any

from app.recommend.filter import FilterRequest

CARD_FIELDS = (
    "id",
    "name",
    "location",
    "cuisines",
    "rating",
    "votes",
    "cost_for_two",
    "veg_type",
    "rest_type",
    "online_order",
    "book_table",
    "dish_liked",
    "listed_types",
)


def normalize_additional_preferences(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def build_candidate_card(
    row: dict[str, Any],
    *,
    include_review_excerpt: bool,
) -> dict[str, Any]:
    cuisines = row.get("cuisines_display") or ""
    if not cuisines:
        tokens = row.get("cuisines") or []
        if isinstance(tokens, (list, tuple)):
            cuisines = ", ".join(str(token) for token in tokens)
        else:
            cuisines = str(tokens)

    card: dict[str, Any] = {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "location": str(row.get("location") or ""),
        "cuisines": cuisines,
        "rating": row.get("rating"),
        "votes": int(row.get("votes") or 0),
        "cost_for_two": row.get("cost_for_two"),
        "veg_type": str(row.get("veg_type") or ""),
        "rest_type": str(row.get("rest_type") or ""),
        "online_order": bool(row.get("online_order")),
        "book_table": bool(row.get("book_table")),
        "dish_liked": str(row.get("dish_liked") or ""),
        "listed_types": list(row.get("listed_types") or []),
    }
    if include_review_excerpt:
        card["review_excerpt"] = str(row.get("review_excerpt") or "")
    return card


def build_prompt(
    request: FilterRequest,
    candidates: list[dict[str, Any]],
    *,
    result_limit: int,
) -> str:
    preferences = normalize_additional_preferences(request.additional_preferences)
    include_excerpt = preferences is not None
    cards = [
        build_candidate_card(row, include_review_excerpt=include_excerpt)
        for row in candidates
    ]

    payload = {
        "preferences": {
            "location": request.location,
            "budget": request.budget,
            "cuisine": request.cuisine,
            "min_rating": request.min_rating,
            "veg_type": request.veg_type,
            "additional_preferences": preferences,
        },
        "candidates": cards,
        "instructions": {
            "rank_only_supplied_ids": True,
            "max_results": result_limit,
            "return_json_only": True,
            "omit_rather_than_invent": True,
        },
    }

    return (
        "Rank restaurants for the user from the candidate list only.\n"
        f"Return at most {result_limit} items.\n"
        "Explain each pick using the preferences and the candidate card fields.\n"
        "Write a one- or two-sentence summary of the set.\n"
        "Return JSON only with this shape:\n"
        '{"summary":"...","recommendations":[{"id":"...","rank":1,"explanation":"..."}]}\n'
        "Do not invent restaurants or ids that are not in the candidate list.\n"
        "Candidate payload:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_repair_prompt(invalid_text: str) -> str:
    return (
        "Your previous reply was not valid JSON for the ranking contract.\n"
        "Return JSON only with keys summary and recommendations.\n"
        "Each recommendation needs id, rank, and explanation.\n"
        "Do not include markdown fences or prose outside the JSON object.\n"
        "Invalid reply to repair:\n"
        f"{invalid_text}"
    )
