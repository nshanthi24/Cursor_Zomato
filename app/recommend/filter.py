"""Hard filters and the pre-rank candidate cap."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.catalog.store import CatalogStore


@dataclass(frozen=True)
class FilterRequest:
    location: str
    budget: str
    cuisine: str
    min_rating: float
    veg_type: str = "any"
    additional_preferences: str | None = None


@dataclass(frozen=True)
class FilterResult:
    candidates: list[dict[str, Any]]
    candidate_count: int
    empty_reason: str | None = None


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _as_str_list(value: object) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if hasattr(value, "tolist"):
        return _as_str_list(value.tolist())
    return [str(value)]


def pre_rank_score(rating: object, votes: object) -> float:
    if _is_missing(rating):
        return float("-inf")
    vote_count = 0 if _is_missing(votes) else int(votes)
    return float(rating) * math.log1p(max(0, vote_count))


def _empty_reason(request: FilterRequest) -> str:
    veg = request.veg_type.casefold()
    veg_part = ""
    if veg and veg != "any":
        veg_part = f", veg_type={request.veg_type!r}"
    return (
        "No rows matched location, cuisine, budget, minimum rating"
        f"{', and veg type' if veg_part else ''} "
        f"(location={request.location!r}, cuisine={request.cuisine!r}, "
        f"budget={request.budget!r}, min_rating={request.min_rating}"
        f"{veg_part})."
    )


def filter_candidates(
    store: CatalogStore,
    request: FilterRequest,
    *,
    candidate_limit: int,
) -> FilterResult:
    """Apply hard filters, then cap by pre-rank score."""
    if candidate_limit < 1:
        raise ValueError("candidate_limit must be a positive integer")

    location = request.location.casefold()
    cuisine = request.cuisine.casefold()
    budget = request.budget.casefold()
    veg_type = (request.veg_type or "any").casefold()

    matched: list[dict[str, Any]] = []
    for row in store.frame.to_dict(orient="records"):
        record = dict(row)
        record["cuisines"] = _as_str_list(record.get("cuisines"))
        record["listed_types"] = _as_str_list(record.get("listed_types"))

        row_location = str(record.get("location") or "").casefold()
        row_area = str(record.get("area") or "").casefold()
        if location not in {row_location, row_area}:
            continue

        cuisine_tokens = [token.casefold() for token in record["cuisines"]]
        if not any(cuisine in token for token in cuisine_tokens):
            continue

        band = record.get("budget_band")
        if _is_missing(band) or str(band).casefold() != budget:
            continue

        if veg_type != "any":
            row_veg = str(record.get("veg_type") or "").casefold()
            if row_veg != veg_type:
                continue

        rating = record.get("rating")
        if _is_missing(rating) or float(rating) < request.min_rating:
            continue

        matched.append(record)

    candidate_count = len(matched)
    if candidate_count == 0:
        return FilterResult(
            candidates=[],
            candidate_count=0,
            empty_reason=_empty_reason(request),
        )

    matched.sort(
        key=lambda row: (
            -pre_rank_score(row.get("rating"), row.get("votes")),
            -int(0 if _is_missing(row.get("votes")) else row.get("votes")),
            str(row.get("name") or ""),
            str(row.get("id") or ""),
        )
    )
    capped = matched[:candidate_limit]
    return FilterResult(
        candidates=capped,
        candidate_count=candidate_count,
        empty_reason=None,
    )


def main() -> None:
    """Exit-check helper against the real catalog snapshot."""
    from app.config import get_settings

    settings = get_settings()
    store = CatalogStore.load(settings)

    known = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
    )
    known_result = filter_candidates(
        store, known, candidate_limit=settings.candidate_limit
    )
    print(
        f"known candidate_count={known_result.candidate_count} "
        f"returned={len(known_result.candidates)}"
    )
    for row in known_result.candidates:
        print(f"  {row['id']} {row['name']} rating={row['rating']} votes={row['votes']}")

    impossible = FilterRequest(
        location="Banashankari",
        budget="low",
        cuisine="Chinese",
        min_rating=5.0,
    )
    empty = filter_candidates(
        store, impossible, candidate_limit=settings.candidate_limit
    )
    print(
        f"impossible candidate_count={empty.candidate_count} "
        f"returned={len(empty.candidates)}"
    )
    print(f"empty_reason={empty.empty_reason}")
