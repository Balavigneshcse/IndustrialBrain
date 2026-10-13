"""IndusMind AI API.

Run (development):  python -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
OpenAPI contract:   /api/v1/openapi.json (interactive docs at /api/v1/docs)
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .api.v1 import api_router
from .api.v1.health import VERSION
from .core.config import INSECURE_DEV_SECRET, get_settings
from .core.errors import install_error_handlers
from .core.logging import RequestContextMiddleware, configure_logging
from .db.session import dispose_engine


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    log = structlog.get_logger("app")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.upload_path.mkdir(parents=True, exist_ok=True)
        if settings.secret_key.get_secret_value() == INSECURE_DEV_SECRET:
            log.warning("insecure_secret_key", hint="set SECRET_KEY in .env (scripts/init-env.ps1)")
        log.info("startup", env=settings.indusmind_env, version=VERSION)
        yield
        await dispose_engine()

    app = FastAPI(
        title="IndusMind AI API", version=VERSION, lifespan=lifespan,
        openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs", redoc_url=None,
        description="Industrial asset intelligence: document evidence, Asset 360, RCA briefs.",
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"],
    )
    app.add_middleware(RequestContextMiddleware)  # added last = outermost: sees every request

    app.include_router(api_router, prefix="/api/v1")
    # Hidden alias so the current UI keeps working until the Phase 4 rebuild switches to /api/v1.
    app.include_router(api_router, prefix="/api", include_in_schema=False)

    Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


app = create_app()
