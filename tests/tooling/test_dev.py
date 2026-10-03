"""Protect local configuration and keep diagnostic output free of secret values."""

import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "dev", Path(__file__).resolve().parents[2] / "scripts/dev.py"
)
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


def test_bootstrap_preserves_existing_local_configuration(tmp_path):
    (tmp_path / ".env.example").write_text("HELIUS_API_KEY=\n")
    original = b"HELIUS_API_KEY=private-existing-value\n"
    (tmp_path / ".env").write_bytes(original)
    assert not dev.create_env(tmp_path)
    assert (tmp_path / ".env").read_bytes() == original


def test_new_configuration_is_private_and_contains_only_placeholders(tmp_path):
    example = "HELIUS_API_KEY=\nTELEGRAM_BOT_TOKEN=\n"
    (tmp_path / ".env.example").write_text(example)
    assert dev.create_env(tmp_path)
    assert (tmp_path / ".env").read_text() == example
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("use_environment", [False, True])
def test_provider_diagnostic_never_discloses_values(tmp_path, monkeypatch, capsys, use_environment):
    secret = "sensitive-value-with-$(shell)-and-spaces"
    (tmp_path / ".env").write_text(f"HELIUS_API_KEY={secret}\n")
    for key in dev.REQUIRED_PROVIDER_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    if use_environment:
        monkeypatch.setenv("HELIUS_API_KEY", secret)
    assert dev.provider_check(tmp_path) == 2
    output = capsys.readouterr().out
    assert secret not in output
    assert "TELEGRAM_BOT_TOKEN" in output
    assert "HELIUS_API_KEY" not in output


def test_all_present_settings_do_not_claim_live_verification(tmp_path, monkeypatch, capsys):
    for key in dev.REQUIRED_PROVIDER_SETTINGS:
        monkeypatch.setenv(key, "configured-but-unverified")
    assert dev.provider_check(tmp_path) == 0
    output = capsys.readouterr().out
    assert "no live request" in output
    assert "configured-but-unverified" not in output


def test_blank_environment_overrides_local_value(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("HELIUS_API_KEY=local-secret\n")
    monkeypatch.setenv("HELIUS_API_KEY", "")
    assert dev.provider_check(tmp_path) == 2
    assert "HELIUS_API_KEY" in capsys.readouterr().out


def test_env_symlink_is_not_overwritten(tmp_path):
    (tmp_path / ".env.example").write_text("HELIUS_API_KEY=\n")
    target = tmp_path / "private-file"
    target.write_text("preserve-me")
    os.symlink(target, tmp_path / ".env")
    assert not dev.create_env(tmp_path)
    assert target.read_text() == "preserve-me"
