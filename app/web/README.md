# Legacy local UI path

The browser UI now lives in [`frontend/`](../../frontend/) so Vercel can host it as a static site.

FastAPI serves that same folder for local all-in-one runs (`GET /` + relative CSS/JS).
