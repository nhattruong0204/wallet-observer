"""Real-capture evidence assertions plus synthetic privacy regression tests."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "solana_fixtures", Path(__file__).resolve().parents[2] / "scripts/solana_fixtures.py"
)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def test_real_captures_match_reviewed_statuses_and_balance_evidence():
    assert fixtures.check(Path(__file__).resolve().parents[1] / "fixtures/solana") == 7


def test_sanitization_preserves_relationships_and_exact_amounts():
    # Deliberately synthetic privacy-test value, not a provider fixture.
    address = "AbCdEfGhJkMnPqRsTuVwXyZ123456789ABCDEFGHJKLMN"
    source = {
        "signature": "2" * 88,
        "owner": address,
        "accounts": [{"pubkey": address}],
        "rawTokenAmount": 2**64 - 1,
        "amount": "123456789123456789123456789123456789",
        "description": address,
        "logMessages": [address],
        "rawData": "private-encoded-instruction",
    }
    result = fixtures.Sanitizer().clean(source)
    assert address not in str(result)
    assert result["owner"] == result["accounts"][0]["pubkey"]
    assert result["rawTokenAmount"] == 2**64 - 1
    assert result["amount"] == source["amount"]
    assert result["signature"].startswith("redacted-")
    assert result["description"] is None and result["logMessages"] is None
    assert result["rawData"] == "[encoded instruction data removed]"


@pytest.mark.parametrize("name,instruction", [("buy", "buy_exact_quote_in"), ("sell", "sell")])
def test_real_swap_actor_differs_from_incidental_watched_account(name, instruction):
    path = Path(__file__).resolve().parents[1] / "fixtures/solana" / f"{name}.json"
    fixture = json.loads(path.read_text())
    trade = next(
        i
        for i in fixture["payload"]["parsed"]["instructions"]
        if i.get("programName") == "pump_amm" and i.get("instructionName") == instruction
    )
    actor = next(a["pubkey"] for a in trade["decoded"]["accounts"] if a["name"] == "user")
    assert actor == fixture["expected"]["actor"]
    assert actor != fixture["expected"]["watched_account"]
    assert not fixture["expected"]["watched_account_is_actor"]


def test_real_routed_swap_retains_unknown_leg_and_transient_wsol():
    path = Path(__file__).resolve().parents[1] / "fixtures/solana/routed-unknown.json"
    fixture = json.loads(path.read_text())
    parsed = fixture["payload"]["parsed"]
    assert fixture["expected"]["classification"] == "unknown.swap"
    assert len(parsed["summary"]["parsedData"]["inner_swaps"]) == 3
    assert any(
        i.get("programName") == "bison_fi" and i.get("decoded") is None
        for i in parsed["instructions"]
    )
    initialized = next(
        i for i in parsed["instructions"] if i.get("instructionName") == "initialize_account_3"
    )
    closed = next(i for i in parsed["instructions"] if i.get("instructionName") == "close_account")
    roles = {a["name"]: a["pubkey"] for a in initialized["decoded"]["accounts"]}
    assert roles["mint"] == "So11111111111111111111111111111111111111112"
    assert roles["account"] == next(
        a["pubkey"] for a in closed["decoded"]["accounts"] if a["name"] == "account"
    )
