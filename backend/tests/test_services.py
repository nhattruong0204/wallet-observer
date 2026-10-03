import asyncio
import time

from fastapi.testclient import TestClient
from wallet_observer.api import create_app
from wallet_observer.worker import WorkerState, create_worker_app, run_worker


def test_api_readiness_changes_without_losing_liveness(settings, tmp_path):
    available = False

    async def database_check(config):
        return available

    with TestClient(create_app(settings, database_check, tmp_path)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        available = True
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/status").json() == {
            "mode": "fixture",
            "database": "ready",
            "collection": "disabled",
            "notifications": "disabled",
        }
        available = False
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200


def test_fixture_status_never_exposes_configured_credentials(settings, tmp_path):
    async def ready(config):
        return True

    with TestClient(create_app(settings, ready, tmp_path)) as client:
        response = client.get("/api/status?api-key=DO_NOT_LOG")
        assert "secret" not in response.text
        assert "DO_NOT_LOG" not in response.text
        assert "database_url" not in response.text


def test_dependency_exception_is_a_redacted_500(settings, tmp_path):
    async def failed(config):
        raise RuntimeError("postgresql://user:DO_NOT_LOG@host/test")

    with TestClient(
        create_app(settings, failed, tmp_path), raise_server_exceptions=False
    ) as client:
        response = client.get("/api/status")
        assert response.status_code == 500
        assert response.json() == {"error": "internal_error"}


def test_built_frontend_is_served_without_hiding_health_routes(settings, tmp_path):
    (tmp_path / "index.html").write_text("<html>Wallet Observer</html>")

    async def ready(config):
        return True

    with TestClient(create_app(settings, ready, tmp_path)) as client:
        assert client.get("/").text == "<html>Wallet Observer</html>"
        assert client.get("/health/ready").status_code == 200
        assert client.get("/api/missing").status_code == 404
        assert client.get("/.env").status_code == 404


def test_worker_recovers_database_and_stops_cleanly(settings):
    async def scenario():
        available = False
        checks = asyncio.Queue()

        async def database_check(config):
            checks.put_nowait(available)
            return available

        state, stop = WorkerState(), asyncio.Event()
        state.task = asyncio.create_task(run_worker(settings, state, stop, database_check))
        assert await asyncio.wait_for(checks.get(), 1) is False
        assert not state.ready(settings)
        available = True
        assert await asyncio.wait_for(checks.get(), 1) is True
        assert state.ready(settings)
        stop.set()
        await asyncio.wait_for(state.task, 1)
        assert not state.ready(settings)

    asyncio.run(scenario())


def test_worker_failed_loop_and_stale_heartbeat_never_report_ready(settings):
    async def scenario():
        async def failed(config):
            raise RuntimeError("DO_NOT_LOG")

        state = WorkerState(database_ready=True, last_check=time.monotonic())
        state.task = asyncio.create_task(run_worker(settings, state, asyncio.Event(), failed))
        await state.task
        assert not state.ready(settings)
        state.task = asyncio.create_task(asyncio.sleep(10))
        state.database_ready = True
        state.last_check = time.monotonic() - 100
        assert not state.ready(settings)
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())


def test_worker_health_endpoints_reflect_dependency_failure(settings):
    async def unavailable(config):
        return False

    with TestClient(create_worker_app(settings, unavailable)) as client:
        assert client.get("/health/live").json() == {"service": "worker", "status": "alive"}
        assert client.get("/health/ready").status_code == 503
