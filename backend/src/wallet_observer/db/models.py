"""Canonical storage inputs, supplied by a qualified normalizer (not implemented here)."""

from datetime import UTC
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)


def exact_decimal(value):
    if isinstance(value, (float, bool)) or not isinstance(value, (int, str, Decimal)):
        raise ValueError("Use an exact integer, decimal or decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("Amount must be a decimal value") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Amount must be finite and nonnegative")
    return result


def exact_raw(value):
    result = exact_decimal(value)
    if result != result.to_integral_value() or result >= Decimal(10) ** 78:
        raise ValueError("Raw amount must be an integer with at most 78 digits")
    return result


RawAmount = Annotated[Decimal, BeforeValidator(exact_raw)]
Value = Annotated[Decimal, BeforeValidator(exact_decimal)]
Address = Annotated[str, Field(min_length=1, max_length=200)]
Chain = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9:_-]{0,63}$")]
Timestamp = Annotated[AwareDatetime, AfterValidator(lambda value: value.astimezone(UTC))]


class StorageInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True, revalidate_instances="always"
    )


class ExecutionLeg(StorageInput):
    token_address: Address
    direction: Literal["in", "out", "fee"]
    raw_quantity: RawAmount
    token_decimals: int = Field(ge=0, le=255, strict=True)

    @field_serializer("raw_quantity", when_used="json")
    def raw_text(self, value):
        return str(int(value))


class CanonicalEvent(StorageInput):
    chain: Chain
    transaction_id: str = Field(min_length=1, max_length=256)
    instruction_index: int = Field(ge=0, strict=True)
    inner_instruction_index: int | None = Field(default=None, ge=0, strict=True)
    wallet_address: Address
    occurred_at: Timestamp | None = None
    kind: Literal[
        "trade.buy",
        "trade.sell",
        "trade.swap",
        "transfer",
        "unknown",
        "unknown.swap",
        "transaction.failed",
    ]
    chain_confirmation: Literal["unknown", "observed", "confirmed", "finalized", "orphaned"]
    source_order_status: str | None = None
    coverage_status: Literal["unknown", "partial", "complete"] = "partial"
    execution_status: Literal["succeeded", "failed", "reverted", "unknown"] | None = None
    execution_usd: Value | None = None
    legs: tuple[ExecutionLeg, ...] = ()
    replay: bool = False

    @field_serializer("execution_usd", when_used="json")
    def value_text(self, value):
        if value is None:
            return None
        # Decimal.normalize() uses the ambient precision and can round a large amount.
        sign, digits, exponent = value.as_tuple()
        while len(digits) > 1 and digits[-1] == 0:
            digits, exponent = digits[:-1], exponent + 1
        return str(Decimal((sign, digits, exponent))) if value else "0"

    @model_validator(mode="after")
    def execution_semantics(self):
        trade = self.kind.startswith("trade.")
        if trade and (
            self.execution_status != "succeeded"
            or not {"in", "out"} <= {leg.direction for leg in self.legs}
            or self.chain_confirmation == "orphaned"
        ):
            raise ValueError("A trade requires successful attributable input and output legs")
        if not trade and self.execution_status == "succeeded":
            raise ValueError(
                "A transfer or unknown/failed event is not a successful trade execution"
            )
        if self.execution_status is None and (self.legs or self.execution_usd is not None):
            raise ValueError("Execution amounts require an execution status")
        return self
