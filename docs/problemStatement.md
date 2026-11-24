# AI-Powered Restaurant Recommendation System

## Project context

This project is an AI-powered restaurant recommendation service inspired by Zomato. It combines a real-world restaurant dataset with a large language model so that suggestions are both data-grounded and written in natural language.

The system does not invent restaurants. It filters the dataset from the user's preferences, then asks an LLM to rank the matching options and explain why each one fits.

## Objective

Build an application that:

1. Takes user preferences such as location, budget, cuisine, and minimum rating.
2. Uses a real-world restaurant dataset.
3. Uses an LLM to produce personalized, human-like recommendations.
4. Shows clear, useful results to the user.

## Data source

- **Dataset:** [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) on Hugging Face.
- **Role:** Source of truth for restaurant facts. Recommendations must come from this data.

Relevant fields to extract and use include:

- Restaurant name
- Location
- Cuisine
- Cost
- Rating
- Any other fields needed to support filtering and explanations

## User input

The application collects:

| Preference | Examples | Required |
| --- | --- | --- |
| Location | Bangalore | Yes |
| Budget | low, medium, high | Yes |
| Cuisine | Italian, Chinese | Yes |
| Minimum rating | numeric threshold | Yes |
| Additional preferences | family-friendly, quick service | Optional free text |

## System workflow

### 1. Data ingestion

- Load the Zomato dataset from Hugging Face.
- Preprocess it so restaurant records are consistent and usable.
- Extract the fields needed for filtering, ranking, and display.

### 2. User input

- Collect location, budget, cuisine, minimum rating, and any extra preferences.
- Treat extra preferences as soft signals the LLM can reason about, since they may not map to a single dataset column.

### 3. Integration layer

- Filter the dataset to restaurants that match the structured preferences (location, budget, cuisine, minimum rating).
- Prepare a compact, structured set of candidate restaurants.
- Pass those candidates into an LLM prompt.
- Design the prompt so the model ranks options and explains the ranking from the supplied data.

### 4. Recommendation engine

The LLM should:

- Rank the candidate restaurants.
- Explain why each recommendation fits the user's preferences.
- Optionally summarize the set of choices.

The model reasons over the filtered candidates. It does not replace the dataset as the source of restaurant facts.

### 5. Output display

Present the top recommendations in a clear format. Each result includes:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- An AI-generated explanation of why it matches

## End-to-end flow

```text
Hugging Face Zomato dataset
        |
        v
Load and preprocess
        |
        v
User preferences
(location, budget, cuisine, min rating, extras)
        |
        v
Filter to candidate restaurants
        |
        v
Structured candidates + prompt
        |
        v
LLM ranks and explains
        |
        v
Top recommendations shown to the user
```

## What success looks like

- Preferences narrow the dataset before the LLM is called.
- Every recommended restaurant exists in the filtered data.
- Displayed name, cuisine, rating, and cost match the dataset.
- Explanations refer to the user's stated preferences.
- The user can read a short list of top matches and understand why each one was chosen.

## Scope

**In scope**

- Loading and preprocessing the Hugging Face Zomato dataset.
- Collecting the preferences listed above.
- Filtering candidates from structured fields.
- Prompting an LLM to rank candidates and write explanations.
- Displaying the top recommendations with the fields listed above.

**Out of scope unless added later**

- Booking, ordering, payments, or user accounts.
- Live Zomato API integration. The dataset is the data source.
- Training or fine-tuning a model. The LLM is used through prompting.
