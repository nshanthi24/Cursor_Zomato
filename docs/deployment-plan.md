# Deployment plan — Vercel (frontend) + Railway (backend)

Target hosting for Thindi:

| Layer | Service | Free tier role |
| --- | --- | --- |
| Static UI | [Vercel](https://vercel.com) | Host HTML / CSS / JS |
| API + catalog + Groq | [Railway](https://railway.app) | Run FastAPI (`uvicorn`) |

Today the app is **one FastAPI process**: Jinja `GET /` plus `/api/*` and `/static/*`. Split hosting needs a small refactor before first deploy.

---

## 1. Target architecture

```text
Browser
  │
  ├─ Vercel  →  index.html, styles.css, app.js
  │                │
  │                │  fetch(API_BASE + "/api/meta")
  │                │  fetch(API_BASE + "/api/recommendations")
  │                ▼
  └─ Railway →  FastAPI
                  GET  /health
                  GET  /api/meta
                  POST /api/recommendations
                  (optional) GET /  kept for local / API-only smoke checks
```

**Source of truth**

- Display facts (name, cuisine, rating, cost, veg) stay on the catalog in Railway memory.
- Groq is called only from Railway. Never put `LLM_API_KEY` in Vercel or any browser-facing env.

---

## 2. Prerequisites

- GitHub (or GitLab) repo with this project pushed
- Vercel account (Hobby / free)
- Railway account (trial / free credits — confirm current Hobby limits)
- Groq API key
- Local catalog build working: `python -m app.catalog` → `data/catalog.parquet`

---

## 3. Pre-deploy code work (do before connecting hosts)

### 3.1 Split the frontend into a static site

Move the Stitch UI into a deployable static folder, for example:

```text
frontend/
  index.html
  styles.css
  app.js
```

Changes vs current Jinja page:

1. **Budget labels** — bake defaults (`500` / `1500`) into the HTML, or load them from `GET /api/meta` if the API already exposes bands.
2. **API base URL** — in `app.js`, prefix calls with a configurable origin, e.g.:

   ```js
   const API_BASE = window.THINDI_API_BASE || "";
   // fetch(`${API_BASE}/api/meta`)
   ```

3. Inject the Railway URL at build / deploy time for Vercel:

   ```html
   <script>window.THINDI_API_BASE = "https://YOUR-SERVICE.up.railway.app";</script>
   ```

   Prefer a Vercel env var + tiny build step that substitutes the value, so you do not hardcode production URLs in git.

4. Keep `app/web/` working for local all-in-one runs (`uvicorn` still serves `/` + `/static`), **or** point local `/` at the same `frontend/` files so there is one UI source.

### 3.2 CORS on Railway

Add FastAPI CORS so the Vercel origin can call the API:

```python
# Allowed origins example
# https://thindi.vercel.app
# http://localhost:3000  (local static preview)
```

Restrict to exact Vercel production (and preview) URLs. Do not use `*` if credentials are ever involved; for this public JSON API, an explicit origin list is enough.

### 3.3 Catalog on Railway

Railway must have `data/catalog.parquet` (and ideally `data/catalog.meta.json`) at runtime.

Pick one approach:

| Option | Pros | Cons |
| --- | --- | --- |
| **A. Commit parquet** (if license / size OK) | Simple deploy | Repo size; regenerate on schema bumps |
| **B. Build on deploy** (`python -m app.catalog` in start / release) | Fresh snapshot | Longer cold start; needs HF download + disk |
| **C. Railway volume + one-time build** | Persistent | Extra setup |

Recommendation for free tier: **A or B**. Prefer **B** if parquet stays out of git; prefer **A** if the file is small and already local-only today.

Ensure `CATALOG_PATH` points at the path used in the container (default `data/catalog.parquet`).

### 3.4 Process / start command

Railway start command (example):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway injects `PORT`. Do not bind `127.0.0.1` in production.

Optional `Dockerfile` or `railway.toml` / Nixpacks Python detection via `pyproject.toml` is fine; pin Python **3.11+**.

### 3.5 Health check

Use existing `GET /health` → `{"status":"ok"}` as the Railway health endpoint.

### 3.6 Secrets

Never commit `.env`. Set secrets only in Railway (and only non-secret public config on Vercel).

---

## 4. Railway — backend deploy

### 4.1 Create service

1. New Railway project → Deploy from GitHub repo.
2. Root directory = repo root (where `pyproject.toml` and `app/` live).
3. Install: `pip install -e .` (or `pip install .`).
4. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. If using option B for catalog, add a release / pre-deploy step:

   ```bash
   python -m app.catalog && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

   Or a two-phase start script that builds only when the snapshot is missing.

### 4.2 Environment variables (Railway)

| Variable | Required | Notes |
| --- | --- | --- |
| `LLM_API_KEY` | Yes | Groq key |
| `LLM_BASE_URL` | No | Default `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | No | Default `openai/gpt-oss-20b` |
| `LLM_TIMEOUT_SECONDS` | No | Default `30` |
| `LLM_SSL_VERIFY` | No | Keep `true` on Railway |
| `DATASET_ID` | No | Defaults in `app/config.py` |
| `DATASET_REVISION` | No | Pin stays as in config |
| `CATALOG_PATH` | No | Default `data/catalog.parquet` |
| `BUDGET_LOW_MAX` / `BUDGET_MEDIUM_MAX` | No | Keep `500` / `1500` unless product changes |
| `CANDIDATE_LIMIT` / `RESULT_LIMIT` | No | Defaults `15` / `5` |
| `CORS_ORIGINS` | Yes (after code support) | Comma-separated Vercel URLs |

Generate a public HTTPS domain in Railway (e.g. `*.up.railway.app`).

### 4.3 Verify backend alone

```text
GET  https://<railway-host>/health
GET  https://<railway-host>/api/meta
POST https://<railway-host>/api/recommendations
     { "location": "...", "cuisine": "...", "budget": "medium",
       "min_rating": 4.0, "veg_type": "any" }
```

Confirm Groq path works and fallback still returns catalog rows if the model fails.

### 4.4 Free-tier notes (Railway)

- Sleep / credit limits may cause cold starts; first request after idle can be slow (catalog load + possible HF build).
- Memory: pandas + full Bangalore catalog must fit; watch OOM on tiny instances.
- Do not enable public logging of request bodies that include user free-text prefs if you care about privacy.

---

## 5. Vercel — frontend deploy

### 5.1 Project setup

1. New Vercel project → same GitHub repo.
2. **Root directory**: `frontend` (or wherever the static files live).
3. Framework preset: **Other**.
4. Build command: none, or a one-line substitute for `THINDI_API_BASE`.
5. Output directory: `.` (static files at root of `frontend/`).

No Node server is required for this UI.

### 5.2 Environment variables (Vercel)

| Variable | Required | Notes |
| --- | --- | --- |
| `THINDI_API_BASE` / `NEXT_PUBLIC_…` style | Yes | Full Railway origin, no trailing slash — e.g. `https://thindi-api.up.railway.app` |

Only this public API origin belongs on Vercel. No Groq key.

### 5.3 CORS handshake

1. Deploy Vercel → note production URL (`https://….vercel.app`).
2. Add that URL (and preview URLs if needed) to Railway `CORS_ORIGINS`.
3. Redeploy Railway if CORS is read only at process start.

### 5.4 Verify frontend

1. Open the Vercel URL.
2. Location / cuisine selects fill from `/api/meta`.
3. Submit → ranked cards from `/api/recommendations`.
4. Browser Network tab: requests go to Railway, status `200`, no CORS errors.

---

## 6. Local parity (after split)

| Goal | Command / setup |
| --- | --- |
| API only | `uvicorn app.main:app --port 8000` |
| Static UI | Serve `frontend/` (e.g. `npx serve frontend`) with `THINDI_API_BASE=http://127.0.0.1:8000` |
| All-in-one (optional) | Keep Jinja `/` for developers who prefer a single port |

---

## 7. Rollout sequence

1. Implement frontend static folder + `API_BASE` in JS.
2. Add CORS middleware + `CORS_ORIGINS` setting.
3. Decide catalog strategy (commit vs build-on-deploy).
4. Deploy Railway → verify `/health`, `/api/meta`, recommendations.
5. Deploy Vercel with `THINDI_API_BASE` → verify UI.
6. Lock CORS to production Vercel URL.
7. Smoke-test veg filter, empty results, and Groq fallback banner.
8. Update README “Run the app” with production URLs and the split workflow.

---

## 8. Acceptance checklist

- [ ] Railway serves `/health` over HTTPS
- [ ] Catalog loads without 503 on `/api/meta`
- [ ] `POST /api/recommendations` returns ≤5 items with catalog-backed fields
- [ ] Groq key exists only on Railway
- [ ] Vercel page loads Stitch dark UI (Playfair / Plus Jakarta, pill filters, numbered cards)
- [ ] Browser calls Railway with CORS success
- [ ] Cold start recovers (health + meta) after Railway idle
- [ ] `.env` / secrets not in git

---

## 9. Out of scope for first deploy

- Custom domains (optional later on both hosts)
- Auth / rate limiting
- CDN caching of `POST /api/recommendations`
- Multi-region catalog replicas
- CI auto-deploy gates beyond Vercel/Railway GitHub integration

---

## 10. Implementation status

Code changes from this plan are in place:

1. `frontend/` static site with `THINDI_API_BASE` via `config.js` / `write-config.mjs`
2. `CORS_ORIGINS` in `Settings` + FastAPI `CORSMiddleware`
3. `Dockerfile`, `railway.toml`, and `scripts/start.sh` (build catalog if missing)
4. `frontend/vercel.json` build that writes `config.js`
5. README deploy / split-local section

Remaining work is host setup only: create Railway + Vercel projects, set secrets, and run the acceptance checklist above.
