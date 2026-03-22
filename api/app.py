"""FastAPI application factory for the Extract Pipeline."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(
        title="Extract Pipeline API",
        version="1.0.0",
        docs_url="/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

    from api.routes import classify, extract, health, schemas

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(schemas.router, prefix="/api", tags=["schemas"])
    app.include_router(classify.router, prefix="/api", tags=["classify"])
    app.include_router(extract.router, prefix="/api", tags=["extract"])

    web_dir = Path(__file__).resolve().parent.parent / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    return app


app = create_app()
