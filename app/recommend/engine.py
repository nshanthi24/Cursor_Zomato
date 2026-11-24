"""Orchestrate filter → prompt → LLM → validation, with catalog fallback."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from app.catalog.store import CatalogStore
from app.config import Settings
from app.llm.client import GroqClient, LLMClient, LLMClientError
from app.recommend.filter import FilterRequest, filter_candidates
from app.recommend.prompt import (
    build_prompt,
    build_repair_prompt,
    normalize_additional_preferences,
)
from app.recommend.validate import (
    ValidatedRecommendation,
    ValidationError,
    parse_model_json,
    validate_recommendations,
)

logger = logging.getLogger(__name__)

FALLBACK_SUMMARY = (
    "These restaurants are ordered by rating and number of votes because a "
    "written recommendation was unavailable."
)
FALLBACK_EXPLANATION = (
    "Ordered by rating and number of votes because a written recommendation "
    "was unavailable."
)


@dataclass(frozen=True)
class EngineResult:
    summary: str
    recommendations: list[ValidatedRecommendation]
    candidate_count: int
    used_fallback: bool
    empty_reason: str | None = None
    dropped_ids: int = 0


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _as_int(value: object) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)


class RecommendationEngine:
    def __init__(
        self,
        store: CatalogStore,
        settings: Settings,
        client: LLMClient | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._client = client or GroqClient(settings)

    def recommend(self, request: FilterRequest) -> EngineResult:
        request = FilterRequest(
            location=request.location,
            budget=request.budget,
            cuisine=request.cuisine,
            min_rating=request.min_rating,
            veg_type=(request.veg_type or "any").strip().casefold() or "any",
            additional_preferences=normalize_additional_preferences(
                request.additional_preferences
            ),
        )
        filtered = filter_candidates(
            self._store,
            request,
            candidate_limit=self._settings.candidate_limit,
        )
        if filtered.candidate_count == 0:
            return EngineResult(
                summary="No restaurants matched these filters.",
                recommendations=[],
                candidate_count=0,
                used_fallback=False,
                empty_reason=filtered.empty_reason,
            )

        prompt = build_prompt(
            request,
            filtered.candidates,
            result_limit=self._settings.result_limit,
        )

        try:
            raw_text = self._complete_with_transport_retry(prompt)
            payload = self._parse_with_repair(raw_text)
            validated = validate_recommendations(
                payload,
                candidates=filtered.candidates,
                store=self._store,
                result_limit=self._settings.result_limit,
            )
            if not validated.recommendations:
                return self._fallback(
                    filtered.candidates,
                    candidate_count=filtered.candidate_count,
                    dropped_ids=validated.dropped_ids,
                )
            return EngineResult(
                summary=validated.summary
                or "Here are restaurants that match your filters.",
                recommendations=validated.recommendations,
                candidate_count=filtered.candidate_count,
                used_fallback=False,
                dropped_ids=validated.dropped_ids,
            )
        except (LLMClientError, ValidationError) as exc:
            logger.info("Using catalog fallback after model failure: %s", exc)
            return self._fallback(
                filtered.candidates,
                candidate_count=filtered.candidate_count,
            )

    def _complete_with_transport_retry(self, prompt: str) -> str:
        try:
            return self._client.complete(prompt)
        except LLMClientError:
            return self._client.complete(prompt)

    def _parse_with_repair(self, raw_text: str) -> dict[str, Any]:
        try:
            return parse_model_json(raw_text)
        except ValidationError:
            repaired = self._client.complete(build_repair_prompt(raw_text))
            try:
                return parse_model_json(repaired)
            except ValidationError as exc:
                raise ValidationError("Repair response was still invalid JSON") from exc

    def _fallback(
        self,
        candidates: list[dict[str, Any]],
        *,
        candidate_count: int,
        dropped_ids: int = 0,
    ) -> EngineResult:
        limited = candidates[: self._settings.result_limit]
        recommendations: list[ValidatedRecommendation] = []
        for row in limited:
            restaurant_id = str(row["id"])
            catalog_row = self._store.get(restaurant_id) or row
            recommendations.append(
                ValidatedRecommendation(
                    id=restaurant_id,
                    name=str(catalog_row.get("name") or ""),
                    cuisines=str(catalog_row.get("cuisines_display") or ""),
                    rating=_as_float(catalog_row.get("rating")),
                    cost_for_two=_as_int(catalog_row.get("cost_for_two")),
                    budget_band=(
                        None
                        if catalog_row.get("budget_band") is None
                        else str(catalog_row.get("budget_band"))
                    ),
                    veg_type=(
                        None
                        if catalog_row.get("veg_type") is None
                        else str(catalog_row.get("veg_type"))
                    ),
                    location=str(catalog_row.get("location") or ""),
                    explanation=FALLBACK_EXPLANATION,
                )
            )
        return EngineResult(
            summary=FALLBACK_SUMMARY,
            recommendations=recommendations,
            candidate_count=candidate_count,
            used_fallback=True,
            dropped_ids=dropped_ids,
        )


def main() -> None:
    """Live exit check against Groq and the real catalog."""
    settings = Settings()  # loads .env
    store = CatalogStore.load(settings)
    engine = RecommendationEngine(store, settings)
    request = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
        additional_preferences="quick service",
    )
    result = engine.recommend(request)
    print(
        f"candidate_count={result.candidate_count} "
        f"used_fallback={result.used_fallback} "
        f"recommendations={len(result.recommendations)}"
    )
    print(f"summary={result.summary}")
    candidate_ids = {
        str(row["id"])
        for row in filter_candidates(
            store, request, candidate_limit=settings.candidate_limit
        ).candidates
    }
    for item in result.recommendations:
        catalog = store.get(item.id)
        assert catalog is not None
        print(
            f"  {item.name} "
            f"in_candidates={item.id in candidate_ids} "
            f"rating_match={item.rating == _as_float(catalog.get('rating'))} "
            f"cost_match={item.cost_for_two == _as_int(catalog.get('cost_for_two'))}"
        )

    blank = settings.model_copy(update={"llm_api_key": ""})
    fallback = RecommendationEngine(store, blank).recommend(request)
    print(
        f"blank_key used_fallback={fallback.used_fallback} "
        f"recommendations={len(fallback.recommendations)}"
    )


if __name__ == "__main__":
    main()
