"""Sanitize reviewed captures and verify the committed source evidence offline."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE58 = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,88}(?![1-9A-HJ-NP-Za-km-z])")
PUBLIC_IDENTIFIERS = {
    "11111111111111111111111111111111",
    "So11111111111111111111111111111111111111112",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "ComputeBudget111111111111111111111111111111",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Sanitizer:
    """Aliases intentionally are not valid chain addresses and must never be queried."""

    def __init__(self):
        self.aliases = {}

    def alias(self, value):
        if value in PUBLIC_IDENTIFIERS:
            return value
        if value not in self.aliases:
            self.aliases[value] = f"redacted-{len(self.aliases) + 1:04d}"
        return self.aliases[value]

    def clean(self, value, field=""):
        if field in {"description", "logMessages", "memo"}:
            return None
        if field in {"rawData", "data"} and isinstance(value, str):
            return "[encoded instruction data removed]"
        if isinstance(value, dict):
            return {key: self.clean(item, key) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item, field) for item in value]
        if isinstance(value, str):
            # Exact amounts are strings too; do not treat a long integer as an address.
            if re.fullmatch(r"-?\d+(?:\.\d+)?", value) and field not in {
                "pubkey",
                "programId",
                "owner",
                "mint",
                "signature",
                "accountKeys",
            }:
                return value
            return BASE58.sub(lambda match: self.alias(match.group()), value)
        return value


def export(capture, row_index, expected, destination):
    """Export one actual history result; no generated provider payloads are accepted."""
    envelope = json.loads(capture.read_text())
    payload = envelope["response"]["data"][row_index]
    sanitizer = Sanitizer()
    sanitized = sanitizer.clean(payload)
    fixture = {
        "provenance": {
            "provider": "Helius",
            "network": "solana-mainnet-beta",
            "endpoint": envelope["endpoint"],
            "captured_at": envelope["captured_at"],
            "private_capture": capture.name,
            "row_index": row_index,
            "original_record_sha256": digest(payload),
            "sanitization": "aliases-v1; free text and encoded instruction data removed",
        },
        "expected": sanitizer.clean(expected),
        "payload": sanitized,
    }
    destination.write_text(json.dumps(fixture, indent=2) + "\n")
    return fixture


def check(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    for entry in manifest["fixtures"]:
        path = directory / entry["file"]
        assert path.parent == directory, "Fixture paths must be direct children"
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"], path.name
        fixture = json.loads(content)
        assert fixture["provenance"]["original_record_sha256"]
        assert fixture["expected"]["classification"]
        assert fixture["expected"]["reason"]
        payload = fixture["payload"]
        assert payload["parserStatus"] == "OK"
        assert payload["parsed"]["transactionStatus"] == fixture["expected"]["transaction_status"]
        meta = payload["rawTransaction"]["meta"]
        assert (meta["err"] is None) == (fixture["expected"]["transaction_status"] == "OK")
        if "stream_payload" in fixture:
            transaction = fixture["stream_payload"]["params"]["result"]["value"]["transaction"]
            assert transaction["signature"] == payload["signature"]
            assert transaction["slot"] == payload["parsed"]["slot"]
            assert fixture["expected"]["unique_signature_count"] == 1
        for item in fixture["expected"].get("balance_checks", []):
            for side in ("pre", "post"):
                balances = meta[f"{side}TokenBalances"]
                match = [b for b in balances if b["accountIndex"] == item["account_index"]]
                assert len(match) <= 1
                amount = match[0]["uiTokenAmount"]["amount"] if match else "0"
                assert amount == item[f"{side}_raw"]
                if match:
                    assert match[0]["owner"] == fixture["expected"]["actor"]

        # Encoded instruction blobs and free text must remain removed.
        def inspect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"description", "logMessages", "memo"}:
                        assert child is None
                    if key in {"rawData", "data"} and isinstance(child, str):
                        assert child == "[encoded instruction data removed]"
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(payload)
        if "stream_payload" in fixture:
            inspect(fixture["stream_payload"])
    return len(manifest["fixtures"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    exporting = commands.add_parser("export")
    exporting.add_argument("capture", type=Path)
    exporting.add_argument("--row", type=int, required=True)
    exporting.add_argument("--expectation", type=Path, required=True)
    exporting.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        count = check(ROOT / "tests/fixtures/solana")
        print(
            f"Verified {count} real capture fixtures, provenance and reviewed balance assertions."
        )
    else:
        export(args.capture, args.row, json.loads(args.expectation.read_text()), args.output)
        print("Sanitized candidate exported. Review privacy and semantics before committing.")


if __name__ == "__main__":
    main()
