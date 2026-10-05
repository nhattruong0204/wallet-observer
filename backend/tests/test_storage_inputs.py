"""Storage input precision is validated before any database connection."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from wallet_observer.db.models import ExecutionLeg


@pytest.mark.parametrize("amount", [0.1, True, -1, "1.5", "NaN", "Infinity", "1e78", "bad", None])
def test_raw_amount_refuses_lossy_invalid_or_fractional_values(amount):
    with pytest.raises(ValidationError):
        ExecutionLeg(token_address="MintAbC", direction="in", raw_quantity=amount, token_decimals=9)


def test_raw_amount_preserves_large_integer_and_address_case():
    amount = "9" * 78
    leg = ExecutionLeg(
        token_address="MintAbC", direction="in", raw_quantity=amount, token_decimals=9
    )
    assert leg.raw_quantity == Decimal(amount)
    assert leg.model_dump(mode="json")["raw_quantity"] == amount
    assert leg.token_address == "MintAbC"


@pytest.mark.parametrize("kind", ["transfer", "unknown", "unknown.swap", "transaction.failed"])
def test_nontrade_event_cannot_claim_a_successful_execution(kind):
    from wallet_observer.db.models import CanonicalEvent

    with pytest.raises(ValidationError, match="not a successful trade"):
        CanonicalEvent(
            chain="solana",
            transaction_id="canonical-test",
            instruction_index=0,
            wallet_address="WalletAbC",
            kind=kind,
            chain_confirmation="confirmed",
            execution_status="succeeded",
        )
