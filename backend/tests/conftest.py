import pytest
from wallet_observer.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name.lower(), raising=False)


@pytest.fixture
def settings():
    return Settings(
        _env_file=None, database_url="postgresql://observer:secret@db/test", worker_poll_seconds=0.1
    )
