"""Parse model JSON and attach catalog facts."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from app.catalog.store import CatalogStore

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ValidatedRecommendation:
    id: str
    name: str
    cuisines: str
    rating: float | None
    cost_for_two: int | None
    budget_band: str | None
    veg_type: str | None
    location: str
    explanation: str


@dataclass(frozen=True)
class ValidationResult:
    summary: str
    recommendations: list[ValidatedRecommendation]
    dropped_ids: int


class ValidationError(ValueError):
    """Raised when model output cannot be parsed into the contract."""


def strip_json_fence(text: str) -> str:
    match = _FENCE_RE.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_model_json(text: str) -> dict[str, Any]:
    cleaned = strip_json_fence(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValidationError("Model output was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Model JSON root must be an object")
    recommendations = payload.get("recommendations")
    if not isinstance(recommendations, list):
        raise ValidationError("Model JSON recommendations must be a list")
    return payload


def _clean_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if value != value:  # NaN
            return None
    except Exception:  # noqa: BLE001
        pass
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _clean_int(value: object) -> int | None:
    number = _clean_number(value)
    if number is None:
        return None
    return int(number)


def _rank_value(item: dict[str, Any]) -> int | None:
    if "rank" not in item:
        return None
    raw = item.get("rank")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    try:
        number = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return None


def validate_recommendations(
    payload: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    store: CatalogStore,
    result_limit: int,
) -> ValidationResult:
    candidate_ids = {str(row["id"]) for row in candidates}
    raw_items = payload.get("recommendations")
    if not isinstance(raw_items, list):
        raise ValidationError("Model JSON recommendations must be a list")

    summary = str(payload.get("summary") or "").strip()

    selected: list[tuple[dict[str, Any], str]] = []
    seen: set[str] = set()
    dropped = 0

    for item in raw_items:
        if not isinstance(item, dict):
            dropped += 1
            continue
        restaurant_id = str(item.get("id") or "").strip()
        if not restaurant_id or restaurant_id not in candidate_ids:
            dropped += 1
            continue
        if restaurant_id in seen:
            dropped += 1
            continue
        seen.add(restaurant_id)
        selected.append((item, restaurant_id))

    ranks = [_rank_value(item) for item, _ in selected]
    if ranks and all(rank is not None for rank in ranks) and len(set(ranks)) == len(ranks):
        ordered = [
            pair
            for _, pair in sorted(
                zip(ranks, selected, strict=True),
                key=lambda pair: pair[0] if pair[0] is not None else 0,
            )
        ]
    else:
        ordered = selected

    ordered = ordered[:result_limit]
    recommendations: list[ValidatedRecommendation] = []
    for item, restaurant_id in ordered:
        row = store.get(restaurant_id)
        if row is None:
            dropped += 1
            continue
        recommendations.append(
            ValidatedRecommendation(
                id=restaurant_id,
                name=str(row.get("name") or ""),
                cuisines=str(row.get("cuisines_display") or ""),
                rating=_clean_number(row.get("rating")),
                cost_for_two=_clean_int(row.get("cost_for_two")),
                budget_band=(
                    None
                    if row.get("budget_band") is None
                    else str(row.get("budget_band"))
                ),
                veg_type=(
                    None if row.get("veg_type") is None else str(row.get("veg_type"))
                ),
                location=str(row.get("location") or ""),
                explanation=str(item.get("explanation") or "").strip(),
            )
        )

    return ValidationResult(
        summary=summary,
        recommendations=recommendations,
        dropped_ids=dropped,
    )
