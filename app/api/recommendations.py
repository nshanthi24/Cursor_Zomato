"""HTTP handlers for catalog metadata and recommendations."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.recommend.engine import EngineResult, RecommendationEngine
from app.recommend.filter import FilterRequest
from app.recommend.validate import ValidatedRecommendation

logger = logging.getLogger(__name__)

BUDGET_BANDS = ("low", "medium", "high")
VEG_FILTERS = ("any", "pure_veg", "veg_and_non_veg")

router = APIRouter()


class MetaResponse(BaseModel):
    locations: list[str]
    cuisines: list[str]
    budget_bands: list[str]
    veg_types: list[str]
    rating_min: float
    rating_max: float
    budget_low_max: int
    budget_medium_max: int


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: str = Field(min_length=1)
    budget: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    min_rating: float
    veg_type: str = "any"
    additional_preferences: str | None = None

    @field_validator("location", "budget", "cuisine", "veg_type", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("additional_preferences", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value


class RecommendationCard(BaseModel):
    id: str
    name: str
    cuisines: str
    rating: float | None
    cost_for_two: int | None
    budget_band: str | None
    veg_type: str | None
    location: str
    explanation: str


class RecommendationMeta(BaseModel):
    candidate_count: int
    used_fallback: bool
    empty_reason: str | None = None


class RecommendationResponse(BaseModel):
    summary: str
    recommendations: list[RecommendationCard]
    meta: RecommendationMeta


def _require_ready_store(request: Request) -> Any:
    store = getattr(request.app.state, "store", None)
    if store is None or not getattr(store, "ready", False):
        raise HTTPException(status_code=503, detail="Catalog is not ready")
    return store


def _canonical_label(value: str, options: list[str], field_name: str) -> str:
    needle = value.casefold()
    for option in options:
        if option.casefold() == needle:
            return option
    raise HTTPException(
        status_code=400,
        detail=f"Unknown {field_name}: {value}",
    )


def _normalize_budget(value: str) -> Literal["low", "medium", "high"]:
    normalized = value.casefold()
    if normalized not in BUDGET_BANDS:
        raise HTTPException(status_code=400, detail=f"Invalid budget: {value}")
    return normalized  # type: ignore[return-value]


def _normalize_veg_type(
    value: str,
) -> Literal["any", "pure_veg", "veg_and_non_veg"]:
    normalized = value.casefold()
    if normalized not in VEG_FILTERS:
        raise HTTPException(status_code=400, detail=f"Invalid veg_type: {value}")
    return normalized  # type: ignore[return-value]


def _card_from_validated(item: ValidatedRecommendation) -> RecommendationCard:
    return RecommendationCard(
        id=item.id,
        name=item.name,
        cuisines=item.cuisines,
        rating=item.rating,
        cost_for_two=item.cost_for_two,
        budget_band=item.budget_band,
        veg_type=item.veg_type,
        location=item.location,
        explanation=item.explanation,
    )


def _response_from_engine(result: EngineResult) -> RecommendationResponse:
    meta = RecommendationMeta(
        candidate_count=result.candidate_count,
        used_fallback=result.used_fallback,
        empty_reason=result.empty_reason,
    )
    return RecommendationResponse(
        summary=result.summary,
        recommendations=[_card_from_validated(item) for item in result.recommendations],
        meta=meta,
    )


@router.get("/api/meta", response_model=MetaResponse)
def get_meta(request: Request) -> MetaResponse:
    store = _require_ready_store(request)
    settings = request.app.state.settings
    return MetaResponse(
        locations=store.locations(),
        cuisines=store.cuisines(),
        budget_bands=list(BUDGET_BANDS),
        veg_types=list(VEG_FILTERS),
        rating_min=0,
        rating_max=5,
        budget_low_max=settings.budget_low_max,
        budget_medium_max=settings.budget_medium_max,
    )


@router.post("/api/recommendations", response_model=RecommendationResponse)
def post_recommendations(
    body: RecommendationRequest,
    request: Request,
) -> RecommendationResponse:
    store = _require_ready_store(request)
    settings = request.app.state.settings

    location = _canonical_label(body.location, store.locations(), "location")
    cuisine = _canonical_label(body.cuisine, store.cuisines(), "cuisine")
    budget = _normalize_budget(body.budget)
    veg_type = _normalize_veg_type(body.veg_type or "any")

    if body.min_rating < 0 or body.min_rating > 5:
        raise HTTPException(status_code=400, detail="min_rating must be between 0 and 5")

    prefs = body.additional_preferences
    if prefs is not None and len(prefs) > settings.additional_preferences_max:
        raise HTTPException(
            status_code=400,
            detail=(
                "additional_preferences exceeds "
                f"{settings.additional_preferences_max} characters"
            ),
        )

    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        engine = RecommendationEngine(store, settings)

    filter_request = FilterRequest(
        location=location,
        budget=budget,
        cuisine=cuisine,
        min_rating=float(body.min_rating),
        veg_type=veg_type,
        additional_preferences=prefs,
    )

    started = time.perf_counter()
    result = engine.recommend(filter_request)
    latency_ms = round((time.perf_counter() - started) * 1000)

    logger.info(
        "recommendations location=%s budget=%s cuisine=%s min_rating=%s "
        "veg_type=%s prefs_len=%s candidate_count=%s used_fallback=%s "
        "dropped_ids=%s latency_ms=%s",
        location,
        budget,
        cuisine,
        body.min_rating,
        veg_type,
        0 if prefs is None else len(prefs),
        result.candidate_count,
        result.used_fallback,
        result.dropped_ids,
        latency_ms,
    )
    return _response_from_engine(result)
