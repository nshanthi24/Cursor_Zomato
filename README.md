# Thindi — Bangalore restaurant recommendations

AI-assisted restaurant recommendations from the Hugging Face Zomato Bangalore catalog. Preferences hard-filter the catalog first. Groq then ranks a short candidate list and writes short explanations. Display facts (name, cuisine, rating, cost) always come from the catalog.

## Requirements

- Python 3.11+
- A Groq API key

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
copy .env.example .env
```

Edit `.env` and set:

```text
LLM_API_KEY=your_groq_api_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-20b
```

If Python TLS verification fails on your machine (common with some corporate proxies), set:

```text
LLM_SSL_VERIFY=false
```

## Build the catalog

Downloads the pinned Hugging Face dataset once, preprocesses it, and writes `data/catalog.parquet`.

```powershell
.venv\Scripts\python -m app.catalog
```

Re-running with the same dataset revision and budget cutoffs reuses the snapshot instead of downloading again.

Delete `data/catalog.parquet` (and `data/catalog.meta.json`) to force a rebuild.

## Run the app

All-in-one (API + UI on one port):

```powershell
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

Split local preview (matches Vercel + Railway):

```powershell
# Terminal 1 — API
$env:CORS_ORIGINS="http://127.0.0.1:3000"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — static UI
$env:THINDI_API_BASE="http://127.0.0.1:8000"
node frontend/write-config.mjs
npx --yes serve frontend -p 3000
```

Useful endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web UI (from `frontend/`) |
| `GET` | `/health` | Process health |
| `GET` | `/api/meta` | Locations, cuisines, budget bands, veg filters |
| `POST` | `/api/recommendations` | Ranked recommendations |

## Deploy (free)

| Layer | Host | Notes |
| --- | --- | --- |
| Frontend | Vercel | Root directory = `frontend`; set `THINDI_API_BASE` to the Railway HTTPS origin |
| Backend | Railway | Dockerfile + `scripts/start.sh`; set `LLM_API_KEY` and `CORS_ORIGINS` to your Vercel URL |

Full steps: [Deployment plan](docs/deployment-plan.md).

## How a request works

1. Hard filters: location, cuisine, budget band, veg preference, minimum rating
2. Cap to the top 15 candidates by `rating * log(1 + votes)`
3. Groq ranks those candidates and writes explanations
4. Validation keeps only candidate ids and joins catalog facts back
5. On model failure, the app falls back to the pre-ranked catalog list

## Tests

```powershell
.venv\Scripts\python -m pytest -q
```

## Project layout

```text
app/                   # FastAPI API, catalog, recommend, LLM
frontend/              # Static UI for Vercel (also served by FastAPI at /)
scripts/start.sh       # Railway start: build catalog if missing, then uvicorn
Dockerfile             # Railway image
data/                  # catalog.parquet (generated)
docs/                  # plans and architecture
```

## Docs

- [Problem statement](docs/problemStatement.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation_plan.md)
- [Deployment plan](docs/deployment-plan.md) (Vercel frontend + Railway backend)
- [Edge cases](docs/edge_case.md)
