"""Independent asynchronous worker lifecycle. Collection/delivery are disabled."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from wallet_observer.database import check_database
from wallet_observer.logging import event
from wallet_observer.settings import Settings


@dataclass
class WorkerState:
    database_ready: bool = False
    last_check: float = 0
    task: asyncio.Task | None = None

    def ready(self, settings):
        fresh = time.monotonic() - self.last_check < (
            settings.worker_poll_seconds + settings.database_timeout_seconds + 1
        )
        return bool(self.task and not self.task.done() and fresh and self.database_ready)


async def run_worker(settings, state, stop, database_check):
    previous = None
    try:
        while not stop.is_set():
            state.database_ready = await database_check(settings)
            state.last_check = time.monotonic()
            if state.database_ready != previous:
                event("database_ready" if state.database_ready else "database_unavailable")
                previous = state.database_ready
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
    except Exception:
        state.database_ready = False
        event("worker_failed")


def create_worker_app(settings: Settings, database_check=check_database):
    state = WorkerState()

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        state.task = asyncio.create_task(run_worker(settings, state, stop, database_check))
        event("service_starting", mode=settings.app_mode)
        try:
            yield
        finally:
            stop.set()
            await state.task
            event("service_stopped")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.worker = state

    @app.get("/health/live")
    async def live():
        return {"service": "worker", "status": "alive"}

    @app.get("/health/ready")
    async def ready():
        available = state.ready(settings)
        return JSONResponse(
            {
                "service": "worker",
                "status": "ready" if available else "not_ready",
                "database": "ready" if state.database_ready else "unavailable",
                "collection": "disabled",
                "notifications": "disabled",
            },
            status_code=200 if available else 503,
        )

    return app
