# Sanitized Solana qualification captures

These are actual Helius mainnet responses captured on 2026-10-03 for issue #2.
They are not copied documentation examples or generated provider messages.
`manifest.json` maps the eight required cases to reviewed files and SHA-256 hashes.

Each file contains original-response provenance, an expected interpretation,
and a sanitized payload. One routed example covers multi-leg execution, temporary
wrapped SOL, and an unsupported leg. `overlap-duplicate.json` contains both an
actual live notification and its subsequent historical delivery using one shared
alias map. It is not a simulated spontaneous WebSocket duplicate.

## Privacy and fidelity

Wallets, signatures, token-account addresses, non-allowlisted program IDs, mints
and blockhashes become stable `redacted-NNNN` aliases within a fixture. Only a small
explicit allowlist of standard public program IDs and WSOL remains literal.
Aliases are intentionally not valid Solana addresses; never query them. Runtime
Solana addresses retain their case; anonymization is solely a fixture operation.

Free-text descriptions, memos and transaction logs are removed. Encoded instruction
data is replaced with an explicit removal marker because it can embed addresses.
Decoded instruction structure, relationships, indexes, status, slots, timestamps,
fees and exact raw balances remain. Raw unredacted captures and the watchlist are
ignored local files, not part of the fixture package.

`original_record_sha256` hashes canonical JSON (sorted keys, compact separators)
before sanitization. The operator can reproduce it from the private capture and
row index. A public reader can check the committed sanitized file hash and its
internal balance evidence, but cannot re-query an aliased signature. These
fixtures do not test raw binary instruction decoding or cryptographic validation.

## Meaning of expected classifications

The buy and sell apply to the decoded PumpSwap `user`, which is different from
the watched account in those two captures. Expected owner balance changes guard
against assigning another participant's execution to the watched wallet. The
incoming transfer is not a buy. The failed transaction has parser success but
execution failure. The routed example stays `unknown.swap` despite a decoded
summary, because not all execution legs are qualified.

The assertions establish reviewed source facts for future implementation. They
do not claim that a production trade classifier has been written in this issue.

## Verification and controlled export

Inside the devcontainer:

```bash
make fixtures
make test
```

To prepare another historical fixture, write a private expected-results JSON
under `local-data/`, select its actual capture row, then use:

```bash
uv run --locked python scripts/solana_fixtures.py export \
  local-data/qualification/RUN/http-001.json --row 0 \
  --expectation local-data/expected.local.json \
  --output local-data/candidate-fixture.json
```

The expectation needs classification, transaction status, rationale, and reviewed
balance checks where applicable. Review privacy and semantics before copying a
candidate here and updating the manifest. Do not fabricate rare cases to fill a
coverage table; record a missing or unsupported case explicitly.
