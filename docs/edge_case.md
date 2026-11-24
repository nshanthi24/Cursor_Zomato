# Edge cases

Corner cases for the restaurant recommendation app. Behavior here follows [architecture.md](architecture.md) and the phase checks in [implementation_plan.md](implementation_plan.md).

Each case has an id so tests can name it. Expected behavior is the rule to implement. Cases marked **accepted** are consequences of the design, not bugs to paper over.

## Catalog ingest and snapshot

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| SNAP-01 | First start, Hugging Face download fails | The process exits. No empty catalog is served. |
| SNAP-02 | `data/catalog.parquet` is missing | Startup fails. Recommendation routes do not answer as if the dataset were empty. |
| SNAP-03 | Parquet exists and its revision matches `DATASET_REVISION` | Load the file. Do not download again. |
| SNAP-04 | Parquet exists but the revision differs from config | Startup fails until the snapshot is rebuilt for the configured revision. |
| SNAP-05 | Parquet exists but the revision sidecar is missing | Treat it as a mismatch. Do not guess that it is current. |
| SNAP-06 | Parquet is unreadable or only partly written | Startup fails. Do not load a partial frame. |
| SNAP-07 | The same revision is preprocessed a second time | Reuse the snapshot instead of downloading. |
| SNAP-08 | The parquet file is deleted | The next start downloads and preprocesses again. |
| SNAP-09 | Restart while Hugging Face is unreachable, snapshot valid | Start from the snapshot. Do not contact Hugging Face. |
| SNAP-10 | Budget cutoffs in config differ from the cutoffs stored on the snapshot | Startup fails or rebuilds. Do not filter with bands that were computed under old thresholds. |
| SNAP-11 | `BUDGET_LOW_MAX` is greater than `BUDGET_MEDIUM_MAX` | Startup fails. The three bands would overlap or invert. |
| SNAP-12 | `CANDIDATE_LIMIT` or `RESULT_LIMIT` is missing, zero, or negative | Startup fails. Both limits are positive integers. |

## Dirty source fields

The train split is about 51,700 Bangalore listings. Ratings, costs, and text fields are strings and are often blank.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| FIELD-01 | `rate` is `4.1/5` | Rating is `4.1`. |
| FIELD-02 | `rate` is `4.1 /5`, `4.1/5 `, or ` 4.1/5` | The numeric portion is parsed. Rating is `4.1`. |
| FIELD-03 | `rate` is `NEW`, `-`, blank, or whitespace | Rating is null. The row stays in the catalog. |
| FIELD-04 | `rate` is outside 0–5, or has no number | Rating is null. |
| FIELD-05 | `rate` is `0/5` or `5/5` | Rating is `0` or `5`. Both are valid. |
| FIELD-06 | Cost is `1,000` or `800` | Cost is the integer `1000` or `800`. |
| FIELD-07 | Cost is blank, `-`, or not a number | Cost is null and `budget_band` is null. The row stays in the catalog. |
| FIELD-08 | Cost is `0` | Cost is `0`, band is `low`. |
| FIELD-09 | Cost is negative | Treat as unparseable. Cost and band are null. |
| FIELD-10 | Cost is exactly `500` | Band is `low`. |
| FIELD-11 | Cost is exactly `501` | Band is `medium`. |
| FIELD-12 | Cost is exactly `1500` | Band is `medium`. |
| FIELD-13 | Cost is exactly `1501` | Band is `high`. |
| FIELD-14 | `cuisines` is `North Indian, Mughlai, Chinese` | Three trimmed tokens. Matching uses the lowercased tokens. Display keeps source casing. |
| FIELD-15 | `cuisines` has spaces, empty slots, or duplicates (`Chinese, Chinese,`) | Trim tokens, drop empties, keep one copy of each token. |
| FIELD-16 | `cuisines` is blank | Cuisine list is empty. The row stays in the catalog and fails every cuisine filter. |
| FIELD-17 | `name` is blank or whitespace | The row is dropped. |
| FIELD-18 | `votes` is missing | Treat votes as `0` for pre-rank. |
| FIELD-19 | `online_order` or `book_table` is `Yes` / `No` | Stored as true / false. |
| FIELD-20 | `online_order` or `book_table` is blank or any other value | Stored as false. |
| FIELD-21 | `dish_liked` or `rest_type` is blank | Card field is empty. The row can still match hard filters. |
| FIELD-22 | `dish_liked` is very long | Stored truncated. The card uses the truncated value. |
| FIELD-23 | `reviews_list` is huge (this column reaches well over a million characters) | It is never written to parquet and never sent whole to the model. |
| FIELD-24 | `reviews_list` is `[]` or blank | `review_excerpt` is empty. |
| FIELD-25 | `reviews_list` has text | `review_excerpt` is at most a few hundred characters. |
| FIELD-26 | `url`, `phone`, `menu_item` are present | Dropped. They are not in the snapshot or the candidate card. |
| FIELD-27 | Leading or trailing whitespace on name, address, location, or area | Stripped before id generation, dedupe, and matching. |

## Dedupe

The same restaurant is listed once per `listed_in(type)` and `listed_in(city)`. Identity is normalized name plus normalized address: trim, casefold, and collapse internal whitespace. Do not strip accents, so `Cafe` and `Café` stay distinct.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| DEDUPE-01 | Two rows share name and address, votes differ | One row remains: the one with more votes. |
| DEDUPE-02 | Two rows share name and address, votes tie | One row remains. The winner is deterministic across runs (stable source order, then listing type). |
| DEDUPE-03 | Duplicate rows have different cuisines or listing types | Cuisines and `listed_in(type)` are unioned, de-duplicated, first-seen order. |
| DEDUPE-04 | Duplicate rows disagree on rating, cost, locality, or area | Those fields come from the winning row only. **Accepted:** a lower-vote listing's area is not kept, so a later location match uses the winner's locality and area. |
| DEDUPE-05 | Same name, different addresses | Two restaurants. They must not collapse. |
| DEDUPE-06 | Same name, both addresses missing | They collapse to one id. **Accepted risk:** unnamed addresses cannot be told apart. |
| DEDUPE-07 | Name differs only by case or repeated spaces | One restaurant. The id uses the normalized name and address. |
| DEDUPE-08 | Preprocess runs twice on the same rows | The same ids and the same surviving row. |
| DEDUPE-09 | Id algorithm | SHA-256 of `casefold(name) + newline + casefold(address)`, hex encoded. Do not use Python's salted `hash()`. |

## Store

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| STORE-01 | Lookup of a known id | Returns that canonical row. |
| STORE-02 | Lookup of an unknown id | Miss. Callers must not invent a row. |
| STORE-03 | The same string is both a locality and an area | It appears once in the location list. |
| STORE-04 | A restaurant has a locality and a different area | Both values are eligible locations. Matching later succeeds on either field. |
| STORE-05 | Location and area are both missing | The row is in the catalog but contributes no location option, so no location filter can select it. |
| STORE-06 | Cuisine tokens differ only by case | One entry in the cuisine list, in a stable display form. |
| STORE-07 | Location and cuisine lists | Sorted, de-duplicated, no blank entries. |
| STORE-08 | Store is still loading | `ready` is false. Recommendation routes return 503. |
| STORE-09 | `GET /health` while the store is not ready | Health may still return 200. It does not mean recommendations can be served. |

## Hard filters

Filters run in order: location, cuisine, budget, minimum rating. A failing row never reaches the model. Filters are not relaxed when the result is empty.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| FILTER-01 | Location differs only by case (`banashankari` vs `Banashankari`) | Match. |
| FILTER-02 | Value equals the restaurant's area but not its locality | Match. |
| FILTER-03 | Value equals the locality but not the area | Match. |
| FILTER-04 | A locality name is also some other restaurant's area | Both restaurants can match. **Accepted:** choosing that label is a locality-or-area search. |
| FILTER-05 | Cuisine is one of several on the row | Match. |
| FILTER-06 | Cuisine differs only by case | Match. |
| FILTER-07 | Requested cuisine is a substring of a token (`Indian` against `North Indian`) | Match. The rule is contains, not exact equality. The form only offers full tokens from `/api/meta`, so this shows up for those tokens and for any value the API has already accepted. |
| FILTER-08 | Requested cuisine is only a prefix fragment and is not itself a meta cuisine | API rejects it with 400 before filtering. See API-06. |
| FILTER-09 | Row has a null rating | Excluded for every minimum rating, including `0`. |
| FILTER-10 | Rating equals `min_rating` | Included. Comparison is greater than or equal. |
| FILTER-11 | Rating is just below `min_rating` | Excluded. |
| FILTER-12 | Null cost or null budget band | Excluded for every budget. There is no "unknown budget" choice. |
| FILTER-13 | Additional preferences are set | They do not change which rows pass. The candidate count matches the same request without that text. |
| FILTER-14 | Additional preferences contradict a hard filter ("cheap" while budget is `high`) | Hard filters win. The text is only a soft hint in the prompt. |
| FILTER-15 | Zero rows survive | Empty candidate list, a reason that names the filters, and no model call. |
| FILTER-16 | A later filter removes the last rows | Still one empty result. Do not retry with a wider location or a lower rating. |

## Pre-rank cap

Score is `rating * log(1 + votes)`. It only chooses which rows are eligible for the model. The model chooses the order the user sees, unless the fallback path is used.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| RANK-01 | Fewer than `CANDIDATE_LIMIT` matches | Send all of them. `candidate_count` equals that size. |
| RANK-02 | Exactly 15 matches | Send all 15. Nothing is dropped. |
| RANK-03 | More than 15 matches | Send the top 15 by score. `candidate_count` stays the pre-cap total, so it can be greater than 15. |
| RANK-04 | `votes` is `0` | Score is `0` because `log(1 + 0)` is 0. The row can still be sent if fewer than 15 rows score higher. |
| RANK-05 | Two rows have the same score | Break ties by votes descending, then name ascending, so the 15th seat does not flip between runs. |
| RANK-06 | One to four matches | The engine may return that many. Do not pad the list with restaurants that failed the filters. |
| RANK-07 | A high-vote row fails a hard filter | It is not pre-ranked back in. |

## Prompt construction

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| PROMPT-01 | No additional preferences | Cards omit `review_excerpt`. |
| PROMPT-02 | Additional preferences are whitespace only | Treat them as absent. Omit `review_excerpt`. |
| PROMPT-03 | Additional preferences are non-empty | Include them in the prompt and attach `review_excerpt` when the row has one. |
| PROMPT-04 | Excerpt, dish list, or name contains quotes, newlines, or braces | The card is serialized as JSON. Do not build the card by pasting text into a JSON string. |
| PROMPT-05 | User text says to ignore instructions or to add a restaurant that is not a candidate | The prompt still lists only candidate ids. Validation drops anything else. |
| PROMPT-06 | A review excerpt contains instructions aimed at the model | Same as PROMPT-05. Excerpt text cannot add an id. |
| PROMPT-07 | More candidates than the cap | The prompt contains at most `CANDIDATE_LIMIT` cards. |
| PROMPT-08 | Card fields | `id`, `name`, `location`, `cuisines`, `rating`, `votes`, `cost_for_two`, `rest_type`, `online_order`, `book_table`, `dish_liked`, `listed_types`. Nothing from `url`, `phone`, or `menu_item`. |

## Model output

A response is usable only after validation. Display facts are then copied from the catalog.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| LLM-01 | JSON matches the contract | Sort by `rank`, cap at `RESULT_LIMIT`, join facts from the catalog. |
| LLM-02 | Valid JSON wrapped in a single ` ```json ` fence | Strip that fence and parse. This does not consume the repair retry. |
| LLM-03 | Prose before or after the JSON, or more than one JSON value | Invalid. One repair call, then fallback if the repair is still unusable. |
| LLM-04 | Not JSON at all | One repair call. The repair prompt includes the bad text. A second failure uses the fallback and does not call the model again. |
| LLM-05 | JSON object missing `recommendations`, or `recommendations` is not a list | Same as invalid JSON: one repair, then fallback. |
| LLM-06 | An id is not in the candidate set | Drop that item. Keep the valid items. Do not fill the gap with the next pre-ranked row. |
| LLM-07 | Every id is unknown, or the list is empty | Fallback. Do not return a summary with an empty card list when candidates existed. |
| LLM-08 | The same valid id appears twice | Keep the first. |
| LLM-09 | More than 5 valid ids | After rank sorting, keep 5. |
| LLM-10 | Fewer valid ids than candidates, some of them valid | Return only the valid ones. A short list is allowed. |
| LLM-11 | `rank` values are unique numbers | Sort ascending by rank. |
| LLM-12 | `rank` is missing, repeated, or not a number | Keep the model's list order for those items. |
| LLM-13 | `rank` is the string `"1"` | Treat it as the number 1. |
| LLM-14 | The model writes a different price, rating, or name inside `explanation` | Keep the explanation text. Overwrite name, cuisines, rating, cost, budget band, and location from the catalog. |
| LLM-15 | `explanation` or `summary` is missing or blank, and at least one id is valid | Return the cards. Do not fallback just because the prose is empty. |
| LLM-16 | Extra JSON keys | Ignore them. |
| LLM-17 | Id matches except for surrounding whitespace | Trim, then apply LLM-06. |
| LLM-18 | Timeout or HTTP error, including 401, 429, and 5xx | Retry the original prompt once. If that retry also fails transport, fallback. |
| LLM-19 | Transport retry returns a body | Validate that body. A parse failure still gets the one repair call from LLM-04. |
| LLM-20 | Worst case for one user request | At most three model calls: one attempt, one transport retry, and one repair. Then fallback. No further calls. |
| LLM-21 | `LLM_API_KEY` is unset or blank, and candidates exist | Do not crash. Fallback, with `used_fallback` true. |
| LLM-22 | The model returns ids in an order that disagrees with the pre-rank | The model's order is the one shown, as long as the response is valid. |

## Fallback

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| FALL-01 | Fallback runs and there are candidates | Top `RESULT_LIMIT` rows in pre-rank order. Facts come from the catalog. |
| FALL-02 | Fallback copy | Summary and each explanation say the list is ordered by rating and votes and that a written recommendation was unavailable. |
| FALL-03 | Fallback flag | `used_fallback` is true. It is false when the model's ids were used, including when some unknown ids were dropped. |
| FALL-04 | Zero candidates | No fallback rows, no model call, `used_fallback` false, `empty_reason` set. |
| FALL-05 | Only two candidates and the model fails | Fallback returns those two, not five invented rows. |

## API

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| API-01 | Body matches the contract and the engine returns cards | 200 with summary, at most 5 recommendations, `candidate_count`, and `used_fallback`. |
| API-02 | Engine returns no rows | 200, `recommendations` empty, `candidate_count` 0, `empty_reason` set, `used_fallback` false. |
| API-03 | Engine uses the fallback | 200 and `used_fallback` true. This is not a 5xx. |
| API-04 | A required field is missing, null, or the body is empty | 400. The engine is not called. |
| API-05 | `location` is not in the meta list, even after casefold (`Not A Place`) | 400. The engine is not called. |
| API-06 | `cuisine` is not in the meta list | 400. The engine is not called. |
| API-07 | Location or cuisine matches a meta value except for case | Accept it and filter with the catalog's value. |
| API-08 | `budget` is `low`, `medium`, or `high` in any case | Accept and normalize to lowercase. |
| API-09 | `budget` is anything else, including `cheap` | 400. |
| API-10 | `min_rating` below 0 or above 5, including `6` | 400. |
| API-11 | `min_rating` is `0`, `5`, or `4.0` | Allowed. `4` and `4.0` are the same rating. |
| API-12 | `min_rating` is a non-numeric string | 400. |
| API-13 | `additional_preferences` omitted | Allowed. |
| API-14 | `additional_preferences` longer than the cap | 400. A value at the cap is allowed. |
| API-15 | Extra JSON fields | Ignore them. |
| API-16 | Store not ready | 503 on `GET /api/meta` and `POST /api/recommendations`. |
| API-17 | `GET /api/recommendations` | 405. The recommendation call is POST only. |
| API-18 | Two identical requests at once | Each runs on its own. The catalog is read-only, so they do not interfere. |
| API-19 | `candidate_count` greater than the number of cards | Allowed. The count is pre-cap; the model only saw 15. |

## Web UI

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| UI-01 | `/api/meta` has not returned yet | Submit stays disabled. The page does not POST an empty form. |
| UI-02 | `/api/meta` returns 503 | Show the unavailable message. Do not render empty selects as if there were no restaurants. |
| UI-03 | Location and cuisine options | Filled only from `/api/meta`, so the normal path cannot submit an unknown value. |
| UI-04 | Budget labels | Show the configured ranges: at or below 500, 501–1,500, and above 1,500. |
| UI-05 | Minimum rating | Input allows 0 through 5 in steps of 0.1. Values outside that never leave the form. |
| UI-06 | Successful response | Summary plus one card per recommendation. Each card shows name, location, cuisine, rating, cost for two, budget band, and explanation. |
| UI-07 | More than five items in the payload | Render at most five. The API already caps this; the page caps again. |
| UI-08 | `used_fallback` true | Show the note that the list was ordered by rating and votes. |
| UI-09 | `used_fallback` false | Do not show that note. |
| UI-10 | Empty recommendations | Show `empty_reason`. Keep the selected location, cuisine, budget, rating, and text. |
| UI-11 | 400 or 503 after submit | Show a clear error. Keep the form values. |
| UI-12 | A second submit before the first returns | The page shows the latest response, not a mix of the two. |
| UI-13 | Explanation mentions a price that is not the catalog price | The card's cost field is still the API's `cost_for_two`. The page does not parse the explanation to correct it. |
| UI-14 | Rating or cost is missing on a returned card | Should not happen after validation. If it does, show the card without substituting 0. |
| UI-15 | Long names, cuisines, or explanations | Wrap inside the card. Do not trim away the rating or the cost. |

## Logging and secrets

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| LOG-01 | A request is handled | Log location, budget, cuisine, minimum rating, candidate count, model latency, fallback use, and how many ids were dropped. |
| LOG-02 | `LLM_API_KEY` is set | It never appears in source, in the snapshot, or in logs. |
| LOG-03 | Additional preferences contain a key-like string | Log the length, not the text. |
| LOG-04 | Review excerpts exist on the row | They are not written to the log. |
| LOG-05 | Model explanation is stored on the response | It may be returned to the caller. It is not required in the application log. |

## Compound cases

These cross more than one stage.

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| MIX-01 | Dedupe keeps a medium-cost row and drops a high-cost duplicate | The restaurant is only in the `medium` band. |
| MIX-02 | User picks an area label, cuisine, band, and a rating that none of those rows reach | 200, empty list, `empty_reason`, model not called. |
| MIX-03 | Sixteen rows match, the model returns five valid ids from those fifteen cards | 200, those five, facts from the catalog, `candidate_count` 16, `used_fallback` false. |
| MIX-04 | Sixteen rows match, the model names a restaurant that was match 16 and therefore not on a card | That id is dropped. The other valid ids are returned. |
| MIX-05 | Rows match, first model call times out, retry is valid | The retry's ranking is shown. `used_fallback` is false. |
| MIX-06 | Rows match, both transport attempts fail | Fallback cards, `used_fallback` true, no further call. |
| MIX-07 | Rows match, body is invalid, repair is valid | The repair's ranking is shown. |
| MIX-08 | Soft text "quick service" on a set that also matches without it | Same `candidate_count`. The prompt differs. Which five are chosen may differ. |
| MIX-09 | Catalog missing, UI is opened | Meta or recommendations return 503. The page explains that results are unavailable. |
| MIX-10 | Snapshot present, process restarted, Hugging Face down | Page works from the snapshot, including a live model call if the provider is up. |
| MIX-11 | Model changes the rating in the explanation and also returns a valid id | The card's rating number equals the store. The explanation string is unchanged. |
| MIX-12 | All candidates have `votes` 0 and equal ratings | Pre-rank tie-break is by name. Fallback order matches that order. |

## Out of scope on purpose

These are not edge cases to implement:

- Booking, accounts, payments, or saved searches.
- Fetching a live Zomato listing when the dataset row looks stale.
- Broadening location, budget, or rating after an empty result.
- Searching the full review text for "family-friendly" or similar phrases.
- Serving cities other than the Bangalore listings in this dataset.
- Treating two restaurants as the same place because their names are similar but their addresses differ.
