"""Hard-filter and pre-rank rules for candidate selection."""

from __future__ import annotations

import math

import pandas as pd

from app.catalog.preprocess import CANONICAL_COLUMNS
from app.catalog.store import CatalogStore
from app.recommend.filter import FilterRequest, filter_candidates, pre_rank_score


def _row(
    *,
    restaurant_id: str,
    name: str,
    location: str,
    area: str,
    cuisines: list[str],
    rating: float | None,
    votes: int,
    cost_for_two: int | None,
    budget_band: str | None,
    veg_type: str = "veg_and_non_veg",
) -> dict[str, object]:
    display = ", ".join(token.title() for token in cuisines)
    return {
        "id": restaurant_id,
        "name": name,
        "location": location,
        "area": area,
        "cuisines": cuisines,
        "cuisines_display": display,
        "rating": rating,
        "votes": votes,
        "cost_for_two": cost_for_two,
        "budget_band": budget_band,
        "veg_type": veg_type,
        "rest_type": "Casual Dining",
        "dish_liked": "",
        "online_order": True,
        "book_table": False,
        "listed_types": ["Delivery"],
        "review_excerpt": "",
    }


def _store(rows: list[dict[str, object]]) -> CatalogStore:
    frame = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    return CatalogStore(frame)


def test_keeps_only_rows_matching_all_hard_filters() -> None:
    store = _store(
        [
            _row(
                restaurant_id="keep",
                name="Keep Me",
                location="Banashankari",
                area="South Bangalore",
                cuisines=["north indian", "chinese"],
                rating=4.2,
                votes=100,
                cost_for_two=800,
                budget_band="medium",
            ),
            _row(
                restaurant_id="wrong-location",
                name="Wrong Location",
                location="Koramangala",
                area="Koramangala",
                cuisines=["chinese"],
                rating=4.5,
                votes=200,
                cost_for_two=800,
                budget_band="medium",
            ),
            _row(
                restaurant_id="wrong-cuisine",
                name="Wrong Cuisine",
                location="Banashankari",
                area="Banashankari",
                cuisines=["italian"],
                rating=4.5,
                votes=200,
                cost_for_two=800,
                budget_band="medium",
            ),
            _row(
                restaurant_id="wrong-budget",
                name="Wrong Budget",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.5,
                votes=200,
                cost_for_two=300,
                budget_band="low",
            ),
            _row(
                restaurant_id="low-rating",
                name="Low Rating",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=3.5,
                votes=200,
                cost_for_two=800,
                budget_band="medium",
            ),
        ]
    )

    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
        ),
        candidate_limit=15,
    )

    assert result.candidate_count == 1
    assert [row["id"] for row in result.candidates] == ["keep"]
    assert result.empty_reason is None


def test_location_matches_locality_or_area_case_insensitive() -> None:
    store = _store(
        [
            _row(
                restaurant_id="by-locality",
                name="Locality Hit",
                location="Banashankari",
                area="Other Area",
                cuisines=["chinese"],
                rating=4.0,
                votes=10,
                cost_for_two=700,
                budget_band="medium",
            ),
            _row(
                restaurant_id="by-area",
                name="Area Hit",
                location="Somewhere Else",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.1,
                votes=11,
                cost_for_two=700,
                budget_band="medium",
            ),
        ]
    )

    result = filter_candidates(
        store,
        FilterRequest(
            location="banashankari",
            budget="medium",
            cuisine="chinese",
            min_rating=4.0,
        ),
        candidate_limit=15,
    )

    assert result.candidate_count == 2
    assert {row["id"] for row in result.candidates} == {"by-locality", "by-area"}


def test_cuisine_matches_one_of_several_tokens_case_insensitive() -> None:
    store = _store(
        [
            _row(
                restaurant_id="multi",
                name="Multi",
                location="Banashankari",
                area="Banashankari",
                cuisines=["north indian", "mughlai", "chinese"],
                rating=4.0,
                votes=5,
                cost_for_two=800,
                budget_band="medium",
            )
        ]
    )

    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="CHINESE",
            min_rating=4.0,
        ),
        candidate_limit=15,
    )
    assert [row["id"] for row in result.candidates] == ["multi"]


def test_null_rating_and_null_budget_are_excluded() -> None:
    store = _store(
        [
            _row(
                restaurant_id="null-rating",
                name="Null Rating",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=None,
                votes=50,
                cost_for_two=800,
                budget_band="medium",
            ),
            _row(
                restaurant_id="null-budget",
                name="Null Budget",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.5,
                votes=50,
                cost_for_two=None,
                budget_band=None,
            ),
            _row(
                restaurant_id="ok",
                name="Ok",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.0,
                votes=5,
                cost_for_two=800,
                budget_band="medium",
            ),
        ]
    )

    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=0.0,
        ),
        candidate_limit=15,
    )

    assert [row["id"] for row in result.candidates] == ["ok"]
    assert result.candidate_count == 1


def test_more_than_limit_is_capped_but_count_is_pre_cap() -> None:
    rows = []
    for index in range(20):
        rows.append(
            _row(
                restaurant_id=f"id-{index:02d}",
                name=f"Place {index:02d}",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.0 + (index / 100.0),
                votes=10 + index,
                cost_for_two=800,
                budget_band="medium",
            )
        )
    store = _store(rows)

    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
        ),
        candidate_limit=15,
    )

    assert result.candidate_count == 20
    assert len(result.candidates) == 15
    scores = [
        pre_rank_score(row["rating"], row["votes"]) for row in result.candidates
    ]
    assert scores == sorted(scores, reverse=True)
    assert result.candidates[0]["id"] == "id-19"


def test_zero_matches_return_empty_reason_and_no_invented_rows() -> None:
    store = _store(
        [
            _row(
                restaurant_id="only",
                name="Only",
                location="Koramangala",
                area="Koramangala",
                cuisines=["italian"],
                rating=4.8,
                votes=100,
                cost_for_two=2000,
                budget_band="high",
            )
        ]
    )

    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
            additional_preferences="quick service",
        ),
        candidate_limit=15,
    )

    assert result.candidates == []
    assert result.candidate_count == 0
    assert result.empty_reason is not None
    assert "location" in result.empty_reason
    assert "cuisine" in result.empty_reason
    assert "budget" in result.empty_reason
    assert "minimum rating" in result.empty_reason


def test_additional_preferences_do_not_change_candidate_count() -> None:
    store = _store(
        [
            _row(
                restaurant_id="a",
                name="A",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.2,
                votes=20,
                cost_for_two=700,
                budget_band="medium",
            )
        ]
    )
    base = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
    )
    soft = FilterRequest(
        location="Banashankari",
        budget="medium",
        cuisine="Chinese",
        min_rating=4.0,
        additional_preferences="family friendly",
    )
    assert (
        filter_candidates(store, base, candidate_limit=15).candidate_count
        == filter_candidates(store, soft, candidate_limit=15).candidate_count
        == 1
    )


def test_pre_rank_score_and_tie_break_are_deterministic() -> None:
    assert pre_rank_score(4.0, 0) == 0.0
    assert math.isclose(pre_rank_score(4.0, 774), 4.0 * math.log1p(774))

    store = _store(
        [
            _row(
                restaurant_id="b",
                name="Bistro",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.0,
                votes=10,
                cost_for_two=700,
                budget_band="medium",
            ),
            _row(
                restaurant_id="a",
                name="Alpha",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.0,
                votes=10,
                cost_for_two=700,
                budget_band="medium",
            ),
        ]
    )
    result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
        ),
        candidate_limit=15,
    )
    assert [row["name"] for row in result.candidates] == ["Alpha", "Bistro"]


def test_veg_type_filter_keeps_matching_rows_only() -> None:
    store = _store(
        [
            _row(
                restaurant_id="pure",
                name="Gokul Veg",
                location="Banashankari",
                area="Banashankari",
                cuisines=["south indian"],
                rating=4.2,
                votes=50,
                cost_for_two=300,
                budget_band="low",
                veg_type="pure_veg",
            ),
            _row(
                restaurant_id="mixed",
                name="Dragon Kitchen",
                location="Banashankari",
                area="Banashankari",
                cuisines=["chinese"],
                rating=4.2,
                votes=60,
                cost_for_two=700,
                budget_band="medium",
                veg_type="veg_and_non_veg",
            ),
        ]
    )

    pure = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="low",
            cuisine="South Indian",
            min_rating=4.0,
            veg_type="pure_veg",
        ),
        candidate_limit=15,
    )
    assert [row["id"] for row in pure.candidates] == ["pure"]

    mixed = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
            veg_type="veg_and_non_veg",
        ),
        candidate_limit=15,
    )
    assert [row["id"] for row in mixed.candidates] == ["mixed"]

    any_result = filter_candidates(
        store,
        FilterRequest(
            location="Banashankari",
            budget="medium",
            cuisine="Chinese",
            min_rating=4.0,
            veg_type="any",
        ),
        candidate_limit=15,
    )
    assert [row["id"] for row in any_result.candidates] == ["mixed"]
