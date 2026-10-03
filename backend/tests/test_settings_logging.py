import json
import logging

import pytest
from wallet_observer.logging import JsonFormatter
from wallet_observer.settings import ConfigurationError, load_settings


def test_fixture_defaults_need_no_provider_credentials(settings):
    assert settings.app_mode == "fixture"
    assert not settings.helius_enabled and not settings.telegram_enabled
    assert settings.helius_api_key.get_secret_value() == ""
    assert "secret" not in repr(settings)


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({}, "DATABASE_URL"),
        ({"database_url": "https://user:DO_NOT_LOG@host/?api-key=DO_NOT_LOG"}, "DATABASE_URL"),
        ({"app_mode": "DO_NOT_LOG"}, "APP_MODE"),
        ({"worker_poll_seconds": "DO_NOT_LOG"}, "WORKER_POLL_SECONDS"),
        ({"helius_enabled": "DO_NOT_LOG"}, "HELIUS_ENABLED"),
        ({"helius_enabled": True, "helius_api_key": "DO_NOT_LOG"}, "SETTINGS"),
        ({"telegram_enabled": True, "telegram_bot_token": "DO_NOT_LOG"}, "SETTINGS"),
    ],
)
def test_invalid_settings_are_useful_but_do_not_contain_values(overrides, field):
    values = (
        {} if not overrides else {"database_url": "postgresql://user:secret@db/test", **overrides}
    )
    with pytest.raises(ConfigurationError) as raised:
        load_settings(_env_file=None, **values)
    assert field in str(raised.value)
    assert "DO_NOT_LOG" not in str(raised.value)
    assert "secret" not in str(raised.value)
    assert "https://" not in str(raised.value)


@pytest.mark.parametrize(
    "feature,credentials,issue",
    [
        ("helius_enabled", {"helius_api_key": "DO_NOT_LOG"}, "#6"),
        (
            "telegram_enabled",
            {"telegram_bot_token": "DO_NOT_LOG", "telegram_chat_id": "123"},
            "#14",
        ),
    ],
)
def test_unimplemented_features_fail_closed_even_with_credentials(feature, credentials, issue):
    with pytest.raises(ConfigurationError) as error:
        load_settings(
            _env_file=None,
            database_url="postgresql://user:secret@db/test",
            app_mode="live",
            **{feature: True},
            **credentials,
        )
    assert issue in str(error.value)
    assert "DO_NOT_LOG" not in str(error.value)


def test_environment_overrides_dotenv_without_exposing_secrets(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("DATABASE_URL=postgresql+psycopg://user:private@db/test\nAPP_MODE=live\n")
    monkeypatch.setenv("APP_MODE", "fixture")
    settings = load_settings(_env_file=path)
    assert settings.app_mode == "fixture"
    assert settings.database_dsn().startswith("postgresql://")
    assert "private" not in repr(settings)


def test_library_messages_arguments_and_tracebacks_are_not_logged():
    secret = "https://user:DO_NOT_LOG@host/path?api-key=DO_NOT_LOG"
    record = logging.LogRecord("uvicorn.error", logging.ERROR, "", 1, secret, (), None)
    record.exc_text = secret
    result = JsonFormatter("api").format(record)
    assert "DO_NOT_LOG" not in result
    assert json.loads(result)["event"] == "library_log"
    assert json.loads(result)["service"] == "api"


def test_application_logs_include_service_and_event_only():
    record = logging.LogRecord("wallet_observer", logging.INFO, "", 1, "unused", (), None)
    record.event = "database_ready"
    record.mode = "fixture"
    record.url = "postgresql://private:secret@host/test"
    output = json.loads(JsonFormatter("worker").format(record))
    assert output["service"] == "worker" and output["event"] == "database_ready"
    assert output["mode"] == "fixture" and "url" not in output


def test_unexpected_library_extras_cannot_break_the_safe_formatter():
    record = logging.LogRecord("library", logging.ERROR, "", 1, "DO_NOT_LOG", (), None)
    record.event = {"secret": "DO_NOT_LOG"}
    record.mode = ["DO_NOT_LOG"]
    output = JsonFormatter("api").format(record)
    assert "DO_NOT_LOG" not in output
    assert json.loads(output)["event"] == "library_log"
