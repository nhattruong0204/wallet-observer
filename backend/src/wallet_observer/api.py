"""HTTP foundation with actual dependency health and an explicit empty state."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from wallet_observer.database import check_database
from wallet_observer.logging import event
from wallet_observer.settings import Settings
from wallet_observer.watches.models import validation_details
from wallet_observer.watches.router import watch_router


class ApplicationStatus(BaseModel):
    mode: Literal["fixture", "live"]
    database: Literal["ready", "unavailable"]
    collection: Literal["disabled"] = "disabled"
    notifications: Literal["disabled"] = "disabled"


def create_app(settings: Settings, database_check=check_database, frontend_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        event("service_starting", mode=settings.app_mode)
        yield
        event("service_stopped")

    app = FastAPI(
        title="Wallet Observer", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )

    @app.middleware("http")
    async def private_watchlist(request, call_next):
        private = request.url.path.startswith(("/api/watches", "/api/groups"))
        if (
            private
            and request.method in {"POST", "PATCH"}
            and (
                request.headers.get("content-type", "").split(";")[0].lower() != "application/json"
            )
        ):
            response = JSONResponse({"detail": "application_json_required"}, status_code=415)
        else:
            response = await call_next(request)
        if private:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse(
            {"detail": "invalid_request", "errors": validation_details(error)}, status_code=422
        )

    app.include_router(watch_router(settings))

    @app.get("/health/live")
    async def live():
        return {"service": "api", "status": "alive"}

    @app.get("/health/ready")
    async def ready():
        available = await database_check(settings)
        return JSONResponse(
            {
                "service": "api",
                "status": "ready" if available else "not_ready",
                "database": "ready" if available else "unavailable",
            },
            status_code=200 if available else 503,
        )

    @app.get("/api/status", response_model=ApplicationStatus)
    async def status():
        return ApplicationStatus(
            mode=settings.app_mode,
            database="ready" if await database_check(settings) else "unavailable",
        )

    @app.exception_handler(Exception)
    async def failed(request, error):
        event("service_failed")
        return JSONResponse({"error": "internal_error"}, status_code=500)

    directory = Path(frontend_dir) if frontend_dir else Path("frontend/dist")
    if (directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    else:

        @app.get("/", include_in_schema=False)
        async def frontend_missing():
            return {"service": "api", "frontend": "Run make frontend or make build."}

    return app
