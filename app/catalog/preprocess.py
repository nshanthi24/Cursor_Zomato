"""Clean, dedupe, and shape the Hugging Face train split."""

from __future__ import annotations

import ast
import hashlib
import math
import re
from collections.abc import Iterable
from typing import Any

import pandas as pd

CANONICAL_COLUMNS = [
    "id",
    "name",
    "location",
    "area",
    "cuisines",
    "cuisines_display",
    "rating",
    "votes",
    "cost_for_two",
    "budget_band",
    "veg_type",
    "rest_type",
    "dish_liked",
    "online_order",
    "book_table",
    "listed_types",
    "review_excerpt",
]

REVIEW_EXCERPT_MAX = 300
DISH_LIKED_MAX = 200

VEG_TYPE_PURE = "pure_veg"
VEG_TYPE_MIXED = "veg_and_non_veg"

_WHITESPACE = re.compile(r"\s+")
_RATING_NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)")
_NON_VEG_NAME = re.compile(r"non[\s-]*veg", re.IGNORECASE)
_PURE_VEG_NAME = re.compile(
    r"pure\s*veg|vegetarian|(?<![A-Za-z])veg(?![A-Za-z])",
    re.IGNORECASE,
)
_NON_VEG_DISH = re.compile(
    r"\b(chicken|mutton|fish|prawn|prawns|seafood|bacon|pork|keema|"
    r"kabab|kebab|lamb|beef|egg|eggs)\b",
    re.IGNORECASE,
)
_NON_VEG_CUISINES = {
    "seafood",
    "bbq",
    "steak",
    "sushi",
    "kebab",
    "kebabs",
    "chicken",
    "mutton",
    "fish",
    "prawn",
    "prawns",
    "pork",
    "roast chicken",
    "grill",
    "bar food",
}


def blank_to_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text if text else None


def normalize_key(value: object) -> str:
    text = blank_to_none(value) or ""
    return _WHITESPACE.sub(" ", text).casefold()


def make_restaurant_id(name: object, address: object) -> str:
    payload = f"{normalize_key(name)}\n{normalize_key(address)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_rating(value: object) -> float | None:
    text = blank_to_none(value)
    if text is None:
        return None
    if text in {"NEW", "-"}:
        return None
    match = _RATING_NUMBER.search(text)
    if match is None:
        return None
    rating = float(match.group(1))
    if rating < 0 or rating > 5:
        return None
    return rating


def parse_cost(value: object) -> int | None:
    text = blank_to_none(value)
    if text is None or text == "-":
        return None
    cleaned = text.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    cost = int(cleaned)
    if cost < 0:
        return None
    return cost


def assign_budget_band(
    cost: int | None, budget_low_max: int, budget_medium_max: int
) -> str | None:
    if cost is None:
        return None
    if cost <= budget_low_max:
        return "low"
    if cost <= budget_medium_max:
        return "medium"
    return "high"


def assign_veg_type(
    name: object,
    cuisines: list[str] | None = None,
    dish_liked: object = None,
) -> str:
    """Derive veg category from name, cuisine tokens, and liked dishes.

    The source dataset has no veg flag. Pure veg is inferred mainly from
    restaurant names; otherwise restaurants are treated as veg and non-veg.
    """
    name_text = blank_to_none(name) or ""
    if _NON_VEG_NAME.search(name_text):
        return VEG_TYPE_MIXED
    if _PURE_VEG_NAME.search(name_text):
        return VEG_TYPE_PURE

    for token in cuisines or []:
        if token.casefold().strip() in _NON_VEG_CUISINES:
            return VEG_TYPE_MIXED

    dish_text = blank_to_none(dish_liked)
    if dish_text and _NON_VEG_DISH.search(dish_text):
        return VEG_TYPE_MIXED

    return VEG_TYPE_MIXED


def parse_cuisines(value: object) -> tuple[list[str], str]:
    text = blank_to_none(value)
    if text is None:
        return [], ""

    normalized: list[str] = []
    display: list[str] = []
    seen: set[str] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
        display.append(token)
    return normalized, ", ".join(display)


def parse_votes(value: object) -> int:
    text = blank_to_none(value)
    if text is None:
        return 0
    try:
        return max(0, int(float(text.replace(",", ""))))
    except ValueError:
        return 0


def parse_yes_no(value: object) -> bool:
    text = blank_to_none(value)
    return text is not None and text.casefold() == "yes"


def truncate(value: object, limit: int) -> str:
    text = blank_to_none(value) or ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def extract_review_excerpt(value: object) -> str:
    text = blank_to_none(value)
    if text is None or text in {"[]", "{}"}:
        return ""

    pieces: list[str] = []
    parsed: Any = None
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError, MemoryError):
        return truncate(text, REVIEW_EXCERPT_MAX)

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pieces.append(str(item[1]))
            elif isinstance(item, str):
                pieces.append(item)
    elif isinstance(parsed, str):
        pieces.append(parsed)

    excerpt = " ".join(_WHITESPACE.sub(" ", piece).strip() for piece in pieces if piece)
    excerpt = excerpt.replace("RATED\\n", " ").replace("RATED\n", " ")
    excerpt = _WHITESPACE.sub(" ", excerpt).strip()
    return truncate(excerpt, REVIEW_EXCERPT_MAX)


def _union_preserve(sequences: Iterable[Iterable[str]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for sequence in sequences:
        for item in sequence:
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def _clean_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_index, record in enumerate(frame.to_dict(orient="records")):
        name = blank_to_none(record.get("name"))
        if name is None:
            continue

        address = blank_to_none(record.get("address")) or ""
        cuisines, cuisines_display = parse_cuisines(record.get("cuisines"))
        display_tokens = [
            token.strip()
            for token in cuisines_display.split(",")
            if token.strip()
        ]
        listed_type = blank_to_none(record.get("listed_in(type)"))
        cost = parse_cost(record.get("approx_cost(for two people)"))

        rows.append(
            {
                "source_index": source_index,
                "id": make_restaurant_id(name, address),
                "name": name,
                "address_key": normalize_key(address),
                "name_key": normalize_key(name),
                "location": blank_to_none(record.get("location")) or "",
                "area": blank_to_none(record.get("listed_in(city)")) or "",
                "cuisines": cuisines,
                "cuisines_display_tokens": display_tokens,
                "rating": parse_rating(record.get("rate")),
                "votes": parse_votes(record.get("votes")),
                "cost_for_two": cost,
                "rest_type": blank_to_none(record.get("rest_type")) or "",
                "dish_liked": truncate(record.get("dish_liked"), DISH_LIKED_MAX),
                "online_order": parse_yes_no(record.get("online_order")),
                "book_table": parse_yes_no(record.get("book_table")),
                "listed_types": [listed_type] if listed_type else [],
                "review_excerpt": extract_review_excerpt(record.get("reviews_list")),
            }
        )
    return rows


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["name_key"], row["address_key"])
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for group in groups.values():
        winner = min(
            group,
            key=lambda row: (
                -row["votes"],
                row["source_index"],
                (row["listed_types"][0] if row["listed_types"] else ""),
            ),
        )
        cuisine_tokens = _union_preserve(item["cuisines"] for item in group)
        display_tokens = _union_preserve(
            item["cuisines_display_tokens"] for item in group
        )
        listed_types = _union_preserve(item["listed_types"] for item in group)

        out.append(
            {
                "id": winner["id"],
                "name": winner["name"],
                "location": winner["location"],
                "area": winner["area"],
                "cuisines": cuisine_tokens,
                "cuisines_display": ", ".join(display_tokens),
                "rating": winner["rating"],
                "votes": winner["votes"],
                "cost_for_two": winner["cost_for_two"],
                "budget_band": None,
                "veg_type": assign_veg_type(
                    winner["name"],
                    cuisine_tokens,
                    winner["dish_liked"],
                ),
                "rest_type": winner["rest_type"],
                "dish_liked": winner["dish_liked"],
                "online_order": winner["online_order"],
                "book_table": winner["book_table"],
                "listed_types": listed_types,
                "review_excerpt": winner["review_excerpt"],
            }
        )
    return out


def preprocess(
    frame: pd.DataFrame,
    *,
    budget_low_max: int,
    budget_medium_max: int,
) -> pd.DataFrame:
    """Return one canonical restaurant row per unique name and address."""
    cleaned = _clean_rows(frame)
    deduped = _dedupe(cleaned)
    for row in deduped:
        row["budget_band"] = assign_budget_band(
            row["cost_for_two"], budget_low_max, budget_medium_max
        )
        row["veg_type"] = assign_veg_type(
            row["name"],
            row.get("cuisines") or [],
            row.get("dish_liked"),
        )

    result = pd.DataFrame(deduped, columns=CANONICAL_COLUMNS)
    if result.empty:
        return result

    result = result.sort_values(["name", "location", "id"], kind="mergesort")
    return result.reset_index(drop=True)
