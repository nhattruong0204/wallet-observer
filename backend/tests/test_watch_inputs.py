"""Address syntax is checked offline; valid bytes do not establish wallet ownership."""

import pytest
from pydantic import ValidationError
from wallet_observer.watches.models import ImportInput, WatchInput, WatchPatch, solana_address


@pytest.mark.parametrize(
    "value",
    [
        "11111111111111111111111111111111",
        "So11111111111111111111111111111111111111112",
    ],
)
def test_known_solana_account_encodings_preserve_case(value):
    assert solana_address(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1" * 31,
        "1" * 33,
        "z" * 44,
        "0" * 32,
        "O" * 32,
        "I" * 32,
        "l" * 32,
        "é" * 32,
        " " + "1" * 32,
        "1" * 32 + "\n",
    ],
)
def test_invalid_encoding_or_decoded_size_is_rejected(value):
    with pytest.raises(ValueError):
        solana_address(value)


@pytest.mark.parametrize(
    "change",
    [
        {"chain": "ethereum"},
        {"chain": "Solana"},
        {"address": 123},
        {"alias": "x" * 121},
        {"note": "x" * 2001},
        {"alias": "a\x00b"},
        {"groups": [" "]},
        {"groups": ["a\x00b"]},
        {"state": "removed"},
        {"state": None},
        {"groups": None},
        {"verified_person": True},
    ],
)
def test_invalid_fields_are_not_coerced_or_silently_discarded(change):
    with pytest.raises(ValidationError):
        WatchInput.model_validate({"address": "1" * 32, **change})


def test_patch_omitted_fields_differ_from_explicit_clear():
    assert WatchPatch().model_dump(exclude_unset=True) == {}
    assert WatchPatch(alias=None, note=None, groups=[]).model_dump(exclude_unset=True) == {
        "alias": None,
        "note": None,
        "groups": [],
    }
    with pytest.raises(ValidationError):
        WatchPatch(state=None)
    with pytest.raises(ValidationError):
        WatchPatch(address="1" * 32)


@pytest.mark.parametrize("version", [0, 2, True, "1", 1.0])
def test_import_version_must_be_integer_one(version):
    with pytest.raises(ValidationError):
        ImportInput(version=version, rows=[])
