"""Preprocess rules for rating, cost, budget bands, cuisines, and dedupe."""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from app.catalog.preprocess import (
    assign_budget_band,
    assign_veg_type,
    make_restaurant_id,
    normalize_key,
    parse_cost,
    parse_cuisines,
    parse_rating,
    preprocess,
)


def test_parse_rating_standard_and_whitespace() -> None:
    assert parse_rating("4.1/5") == 4.1
    assert parse_rating("4.1 /5") == 4.1
    assert parse_rating("4.1/5 ") == 4.1
    assert parse_rating(" 4.1/5") == 4.1
    assert parse_rating("0/5") == 0.0
    assert parse_rating("5/5") == 5.0


@pytest.mark.parametrize(
    "value",
    ["NEW", "-", "", "   ", None, "6/5", "-1/5", "nope", "Rated"],
)
def test_parse_rating_null_cases(value: object) -> None:
    assert parse_rating(value) is None


def test_parse_cost_commas_and_blanks() -> None:
    assert parse_cost("1,000") == 1000
    assert parse_cost("800") == 800
    assert parse_cost("0") == 0
    assert parse_cost("") is None
    assert parse_cost("   ") is None
    assert parse_cost("-") is None
    assert parse_cost(None) is None
    assert parse_cost("abc") is None
    assert parse_cost("-100") is None


def test_budget_bands_at_boundaries() -> None:
    assert assign_budget_band(500, 500, 1500) == "low"
    assert assign_budget_band(501, 500, 1500) == "medium"
    assert assign_budget_band(1500, 500, 1500) == "medium"
    assert assign_budget_band(1501, 500, 1500) == "high"
    assert assign_budget_band(0, 500, 1500) == "low"
    assert assign_budget_band(None, 500, 1500) is None


def test_assign_veg_type_from_name_cuisine_and_dishes() -> None:
    assert assign_veg_type("Gokul Veg", ["south indian"], "") == "pure_veg"
    assert assign_veg_type("Brundhavana Pure Veg", [], "") == "pure_veg"
    assert assign_veg_type("SGS Non Veg", ["south indian"], "") == "veg_and_non_veg"
    assert assign_veg_type("Dragon", ["seafood"], "") == "veg_and_non_veg"
    assert assign_veg_type("Cafe", ["cafe"], "Chicken Wings") == "veg_and_non_veg"
    assert assign_veg_type("Mystery Place", ["north indian"], "") == "veg_and_non_veg"


def test_parse_cuisines_keeps_display_and_normalized_tokens() -> None:
    normalized, display = parse_cuisines("North Indian, Mughlai, Chinese")
    assert normalized == ["north indian", "mughlai", "chinese"]
    assert display == "North Indian, Mughlai, Chinese"

    normalized, display = parse_cuisines("Chinese, Chinese, , Thai")
    assert normalized == ["chinese", "thai"]
    assert display == "Chinese, Thai"

    normalized, display = parse_cuisines("")
    assert normalized == []
    assert display == ""


def test_restaurant_id_is_stable_sha256() -> None:
    expected = hashlib.sha256("jalsa\n942, 21st main road".encode("utf-8")).hexdigest()
    assert make_restaurant_id("Jalsa", "942, 21st Main Road") == expected
    assert make_restaurant_id("  Jalsa  ", "942,  21st   Main Road") == expected
    assert make_restaurant_id("Jalsa", "A") != make_restaurant_id("Jalsa", "B")
    assert make_restaurant_id("Cafe", "") != make_restaurant_id("Café", "")


def test_normalize_key_collapses_whitespace_and_casefolds() -> None:
    assert normalize_key("  Spice   Elephant ") == "spice elephant"


def _raw_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        "url",
        "address",
        "name",
        "online_order",
        "book_table",
        "rate",
        "votes",
        "phone",
        "location",
        "rest_type",
        "dish_liked",
        "cuisines",
        "approx_cost(for two people)",
        "reviews_list",
        "menu_item",
        "listed_in(type)",
        "listed_in(city)",
    ]
    return pd.DataFrame(rows, columns=columns)


def test_dedupe_keeps_higher_votes_and_unions_listing_types() -> None:
    frame = _raw_frame(
        [
            {
                "name": "Jalsa",
                "address": "942, 21st Main Road",
                "location": "Banashankari",
                "listed_in(city)": "Banashankari",
                "rate": "4.1/5",
                "votes": 100,
                "approx_cost(for two people)": "800",
                "cuisines": "North Indian, Chinese",
                "listed_in(type)": "Buffet",
                "online_order": "Yes",
                "book_table": "Yes",
                "rest_type": "Casual Dining",
                "dish_liked": "Pasta",
                "reviews_list": "[('Rated 4.0', 'RATED\\n Great buffet and service.')]",
                "url": "http://example/a",
                "phone": "000",
                "menu_item": "[]",
            },
            {
                "name": "Jalsa",
                "address": "942, 21st Main Road",
                "location": "Banashankari",
                "listed_in(city)": "Banashankari",
                "rate": "3.9/5",
                "votes": 775,
                "approx_cost(for two people)": "900",
                "cuisines": "Mughlai",
                "listed_in(type)": "Delivery",
                "online_order": "No",
                "book_table": "No",
                "rest_type": "Casual Dining",
                "dish_liked": "Biryani",
                "reviews_list": "[]",
                "url": "http://example/b",
                "phone": "111",
                "menu_item": "[]",
            },
        ]
    )

    result = preprocess(frame, budget_low_max=500, budget_medium_max=1500)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["name"] == "Jalsa"
    assert row["votes"] == 775
    assert row["rating"] == 3.9
    assert row["cost_for_two"] == 900
    assert row["budget_band"] == "medium"
    assert row["cuisines"] == ["north indian", "chinese", "mughlai"]
    assert set(row["listed_types"]) == {"Buffet", "Delivery"}
    assert "reviews_list" not in result.columns
    assert "url" not in result.columns
    assert "phone" not in result.columns
    assert "menu_item" not in result.columns


def test_blank_name_dropped_missing_rating_kept() -> None:
    frame = _raw_frame(
        [
            {
                "name": "   ",
                "address": "Somewhere",
                "location": "Banashankari",
                "listed_in(city)": "Banashankari",
                "rate": "4.0/5",
                "votes": 10,
                "approx_cost(for two people)": "500",
                "cuisines": "Chinese",
                "listed_in(type)": "Delivery",
                "online_order": "Yes",
                "book_table": "No",
                "rest_type": "Quick Bites",
                "dish_liked": "",
                "reviews_list": "[]",
                "url": "",
                "phone": "",
                "menu_item": "[]",
            },
            {
                "name": "No Rating Spot",
                "address": "1 Main",
                "location": "Banashankari",
                "listed_in(city)": "Banashankari",
                "rate": "NEW",
                "votes": 0,
                "approx_cost(for two people)": "",
                "cuisines": "",
                "listed_in(type)": "Dine-out",
                "online_order": "Maybe",
                "book_table": "",
                "rest_type": "",
                "dish_liked": "",
                "reviews_list": "[]",
                "url": "",
                "phone": "",
                "menu_item": "[]",
            },
        ]
    )

    result = preprocess(frame, budget_low_max=500, budget_medium_max=1500)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["name"] == "No Rating Spot"
    assert pd.isna(row["rating"])
    assert pd.isna(row["cost_for_two"])
    assert pd.isna(row["budget_band"])
    assert row["online_order"] == False
    assert row["book_table"] == False
    assert row["review_excerpt"] == ""


def test_same_name_different_address_stays_two_rows() -> None:
    frame = _raw_frame(
        [
            {
                "name": "Cafe Coffee Day",
                "address": "Road A",
                "location": "A",
                "listed_in(city)": "Banashankari",
                "rate": "3.5/5",
                "votes": 10,
                "approx_cost(for two people)": "300",
                "cuisines": "Cafe",
                "listed_in(type)": "Cafes",
                "online_order": "Yes",
                "book_table": "No",
                "rest_type": "Cafe",
                "dish_liked": "",
                "reviews_list": "[]",
                "url": "",
                "phone": "",
                "menu_item": "[]",
            },
            {
                "name": "Cafe Coffee Day",
                "address": "Road B",
                "location": "B",
                "listed_in(city)": "Banashankari",
                "rate": "3.6/5",
                "votes": 12,
                "approx_cost(for two people)": "350",
                "cuisines": "Cafe",
                "listed_in(type)": "Cafes",
                "online_order": "Yes",
                "book_table": "No",
                "rest_type": "Cafe",
                "dish_liked": "",
                "reviews_list": "[]",
                "url": "",
                "phone": "",
                "menu_item": "[]",
            },
        ]
    )

    result = preprocess(frame, budget_low_max=500, budget_medium_max=1500)
    assert len(result) == 2
    assert set(result["location"]) == {"A", "B"}


def test_review_excerpt_is_short_and_not_raw_list() -> None:
    long_text = "A" * 1000
    frame = _raw_frame(
        [
            {
                "name": "Excerpt Place",
                "address": "1 Road",
                "location": "Banashankari",
                "listed_in(city)": "Banashankari",
                "rate": "4.0/5",
                "votes": 5,
                "approx_cost(for two people)": "600",
                "cuisines": "Chinese",
                "listed_in(type)": "Delivery",
                "online_order": "Yes",
                "book_table": "No",
                "rest_type": "Casual Dining",
                "dish_liked": "X" * 500,
                "reviews_list": f"[('Rated 4.0', 'RATED\\n {long_text}')]",
                "url": "",
                "phone": "",
                "menu_item": "[]",
            }
        ]
    )

    result = preprocess(frame, budget_low_max=500, budget_medium_max=1500)
    excerpt = result.iloc[0]["review_excerpt"]
    dish = result.iloc[0]["dish_liked"]
    assert excerpt
    assert len(excerpt) <= 300
    assert "reviews_list" not in excerpt
    assert len(dish) <= 200
