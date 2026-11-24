"""Application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.recommendations import router as recommendations_router
from app.catalog.store import CatalogStore, CatalogStoreError
from app.config import Settings, get_settings
from app.recommend.engine import RecommendationEngine

logger = logging.getLogger("uvicorn.error")

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT.parent / "frontend"


def _frontend_file(name: str) -> Path:
    path = FRONTEND_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Missing frontend file: {name}")
    return path


def create_app(
    settings: Settings | None = None,
    store: CatalogStore | None = None,
    engine: RecommendationEngine | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        if store is not None:
            app.state.store = store
        else:
            try:
                app.state.store = CatalogStore.load(settings)
            except CatalogStoreError as exc:
                logger.warning("Catalog store is not ready: %s", exc)
                app.state.store = SimpleNamespace(ready=False)
        app.state.engine = engine
        if getattr(app.state.store, "ready", False):
            logger.info(
                "Catalog ready with %s restaurants",
                len(app.state.store),
            )
        else:
            logger.warning("Catalog store is not ready")
        yield

    app = FastAPI(title="Thindi recommendations", lifespan=lifespan)

    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(recommendations_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.errors()})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if FRONTEND_DIR.is_dir():
        @app.get("/")
        def home() -> FileResponse:
            return FileResponse(_frontend_file("index.html"))

        @app.get("/styles.css")
        def frontend_styles() -> FileResponse:
            return FileResponse(_frontend_file("styles.css"), media_type="text/css")

        @app.get("/app.js")
        def frontend_app_js() -> FileResponse:
            return FileResponse(
                _frontend_file("app.js"),
                media_type="application/javascript",
            )

        @app.get("/config.js")
        def frontend_config_js() -> FileResponse:
            return FileResponse(
                _frontend_file("config.js"),
                media_type="application/javascript",
            )

    return app


app = create_app()
