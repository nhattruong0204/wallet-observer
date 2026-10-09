"""Private watchlist input contracts; labels never imply verified identity."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

State = Literal["active", "paused", "resolving", "unsupported", "error"]
GroupName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00]+$"),
]
Groups = Annotated[list[GroupName], Field(max_length=50)]
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def solana_address(value: str) -> str:
    if not 32 <= len(value) <= 44 or any(char not in BASE58 for char in value):
        raise ValueError("Requires a base58-encoded 32-byte Solana address")
    number = 0
    for char in value:
        number = number * 58 + BASE58.index(char)
    size = len(value) - len(value.lstrip("1")) + (number.bit_length() + 7) // 8
    if size != 32:
        raise ValueError("Requires a base58-encoded 32-byte Solana address")
    return value


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class WatchPatch(Input):
    alias: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    state: State | None = None
    groups: Groups | None = None

    @field_validator("alias", "note")
    @classmethod
    def no_nul(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("NUL characters are not allowed")
        return value

    @field_validator("state", "groups")
    @classmethod
    def explicit_values(cls, value):
        if value is None:
            raise ValueError("State and groups cannot be null")
        return value


class WatchInput(WatchPatch):
    chain: Literal["solana"] = "solana"
    address: str
    state: State = "active"
    groups: Groups = Field(default_factory=list)

    @field_validator("address")
    @classmethod
    def address_format(cls, value):
        return solana_address(value)


class GroupInput(Input):
    name: GroupName


class ImportInput(Input):
    version: int = Field(ge=1, le=1)
    rows: list[object] = Field(max_length=1000)


def validation_details(error):
    """Return fixed field names and error codes, never submitted values or context."""
    fields = {
        "body",
        "path",
        "query",
        "chain",
        "address",
        "alias",
        "note",
        "state",
        "groups",
        "name",
        "version",
        "rows",
        "watch_id",
        "group_id",
        "include_removed",
    }
    return [
        {
            "field": ".".join(
                str(p) if p in fields or isinstance(p, int) else "field" for p in item["loc"]
            ),
            "code": item["type"],
            "message": item["msg"],
        }
        for item in error.errors()
    ]
