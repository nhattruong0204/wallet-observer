# Personal watchlist API and interchange format

Implemented for [WO-005 / #5](https://github.com/nhattruong0204/wallet-observer/issues/5).
The API manages one operator's manual Solana watch scope in PostgreSQL. It works
in fixture mode without provider credentials. The desktop watchlist UI is #12;
provider subscriptions and reconciliation are #6. These endpoints do not make
provider calls or assert that collection is running.

## Addresses, labels and state

Only the exact chain name `solana` is accepted. An address must be a case-sensitive
base58 encoding of exactly 32 bytes; surrounding whitespace, invalid characters,
wrong decoded lengths and unsupported chains are rejected. This is syntax
validation, not an account-existence, curve, ownership or identity check. Solana
program-derived addresses are not rejected merely for being off curve. See the
[Solana account address contract](https://solana.com/docs/core/accounts#account-address).

A watch has a stable UUID and one unique wallet identity `(chain, address)`.
Alias (nullable, at most 120 characters) and note (nullable, at most 2,000) are
manual text. Responses label them `label_source: manual`; writing them never
creates a verified source identity or an identity-wallet link. NUL is rejected.

| State         | Meaning for this API                           | Collection intent                         |
| ------------- | ---------------------------------------------- | ----------------------------------------- |
| `active`      | Operator requests monitoring                   | Included once                             |
| `paused`      | Operator temporarily stops monitoring          | Excluded                                  |
| `resolving`   | Waiting for an operator/source resolution step | Excluded                                  |
| `unsupported` | Explicitly marked unsupported                  | Excluded                                  |
| `error`       | Explicitly marked as needing attention         | Excluded                                  |
| `removed`     | Soft-removed through DELETE                    | Excluded; hidden from default list/export |

The API records the selected state; it does not fabricate resolution results or
provider acknowledgements. New watches default to `active`. In fixture mode this
is saved intent only: `/api/status` and the intent response still report
`collection: disabled`. Only #6 can reconcile this desired scope into real
subscriptions, including disconnect races and provider limits.

Pause and removal preserve the wallet, watch ID, aliases, notes, groups and all
historical events, revisions, payloads and checkpoints. Restore a removed watch
explicitly with PATCH state `active` or `paused`. Repeating POST or import for an
existing watch, including a removed one, returns a duplicate and preserves its
state/metadata. An addition is never an implicit resume or edit.

## HTTP contract

| Method and path                      | Behavior                                                                                                                                                                                                                          |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/watches`                   | List non-removed watches, ordered by chain/address. `include_removed=true` includes removed records; optional UUID `group_id` filters memberships. Unknown group filters return an empty list.                                    |
| `POST /api/watches`                  | Create a watch: 201 with `{created: true, watch: ...}`. Existing identity: 200 with `created: false`, no changes.                                                                                                                 |
| `GET /api/watches/{id}`              | Return `{watch: ...}`, including a removed watch when addressed directly.                                                                                                                                                         |
| `PATCH /api/watches/{id}`            | Edit alias, note, state or replace group membership. Omitted fields stay unchanged; null clears alias/note; `groups: []` clears memberships. State/groups cannot be null. Chain/address/ID are immutable. Empty PATCH is a no-op. |
| `DELETE /api/watches/{id}`           | Soft-remove; 204, including repeated removal. Unknown watch: 404.                                                                                                                                                                 |
| `GET /api/watches/collection-intent` | Return `{collection: "disabled", watches: [...]}` with unique active Solana watch/wallet IDs and addresses. This is desired scope, not an acknowledgement of a running provider subscription.                                     |
| `GET /api/groups`                    | List stable group UUIDs and names, including empty groups.                                                                                                                                                                        |
| `POST /api/groups`                   | Create group: 201; identical normalized name: 200 with existing group.                                                                                                                                                            |
| `PATCH /api/groups/{id}`             | Rename in place; members retain the same group ID. Name conflict: 409, no changes.                                                                                                                                                |
| `DELETE /api/groups/{id}`            | Delete group and its membership links only; watches, states and history remain. 204, or 404 if absent.                                                                                                                            |
| `POST /api/watches/import/preview`   | Validate a versioned batch without writes; report every row.                                                                                                                                                                      |
| `POST /api/watches/import/apply`     | Revalidate and atomically apply valid new rows, explicitly reporting skipped duplicates. Any invalid row rejects the whole batch.                                                                                                 |
| `GET /api/watches/export`            | Download the complete non-removed watch scope in version 1 format.                                                                                                                                                                |

POST/PATCH require `Content-Type: application/json` (415 otherwise). UUID or model
validation errors return 422 with fixed field paths, error codes and messages,
without submitted values. Unknown records return 404; group-name collisions
return 409. Storage/lock/commit failures return redacted 503. Neither database
exception text nor private input is written to application logs. Successful
responses are sent only after transaction commit.

Groups are referenced by portable names in watch input/export. Names are trimmed,
case-sensitive and 1–80 characters; NUL is rejected. A watch accepts up to 50 group
names, with repeats collapsed into one membership. Missing groups are created
within the watch transaction. A rename updates the name returned by list/export;
a later import using the old name creates that distinct group for new watches.
Duplicate-watch imports do not overwrite or merge any existing metadata/groups.

## Version 1 JSON

This is a template, not a valid chosen wallet or source fixture. Replace the
address with an operator-selected Solana address before submission:

```json
{
  "version": 1,
  "rows": [
    {
      "chain": "solana",
      "address": "<SOLANA_WALLET_ADDRESS>",
      "alias": "My manual label",
      "note": null,
      "state": "paused",
      "groups": ["Research"]
    }
  ]
}
```

The integer version must be 1. Each row uses the POST watch fields. Unknown fields
are rejected. Only `address` is required in each row; chain defaults to `solana`,
state to `active`, alias/note to null and groups to empty. A batch holds 0–1,000
rows; this bounds work per request, not the operator's total watchlist or a
commercial quota. Empty batches are successful no-ops. Export omits database IDs,
created timestamps and derived identity labels, so it can import into a fresh
watchlist. Removed entries and empty groups are not exported.

Preview returns `applied: false`, counts for `valid`, `duplicate`, `invalid`, and
one report per 1-based row. Invalid rows include redacted field errors. Duplicates
identify `existing` (with watch ID/state) or `earlier_row`. For repeated identities
in a file, the first valid new row wins; later rows do not overwrite it. Invalid
rows remain invalid even if they contain a duplicate address.

Apply accepts the same envelope and rechecks against current database state; a
preview is advisory, not a reservation. On invalid input it returns 422 with
`detail.code: invalid_import`, `applied: false` and the full row report, committing
nothing. On success it returns `applied: true`, the same counts/statuses and watch
IDs for newly applied rows. Duplicates are explicitly skipped. A late database
failure rolls back all new wallets, watches, groups and memberships and returns
503; retrying the entire batch is safe.

All operator mutations take the same transaction-scoped table locks before
reading/changing watches and groups. This serializes rare single-operator writes
and allows ordinary reads to continue. The existing unique constraints remain
the identity guarantee. Revisit lock granularity only if contention is measured;
no subscription/outbox service is added for this issue.

## Initial private list and local use

The initial operating target is an explicit owner-selected list of **10–25
Solana wallets**. No personal list was supplied for this implementation, and none
is embedded in source, tests, Docker images or acceptance logs. Tests exercise a
25-row batch of clearly identified synthetic address encodings; those are not an
approved operational watchlist and are never sent to a provider.

On 2026-10-09 the owner explicitly deferred selecting/importing this list so the
API issue can finish. The existing first-live trial in
[#18](https://github.com/nhattruong0204/wallet-observer/issues/18) still requires
10–25 selected wallets; use this procedure before that trial.

Keep the real versioned file under ignored `local-data/watchlist.json`, directory
mode 0700 and file mode 0600. In the devcontainer, with `make migrate` and `make api`
(or `make dev`) running, validate its count without printing addresses:

```bash
python - <<'PY'
import json
from pathlib import Path
batch = json.loads(Path("local-data/watchlist.json").read_text())
assert batch["version"] == 1 and 10 <= len(batch["rows"]) <= 25
print("Initial list count is within the 10–25 wallet target.")
PY
curl --fail-with-body --silent --show-error \
  -H 'Content-Type: application/json' --data-binary @local-data/watchlist.json \
  http://127.0.0.1:8000/api/watches/import/preview
```

Review all row statuses and correct invalid/duplicate entries until there are
10–25 distinct valid new wallets for an empty initial scope. Then apply the same
file and inspect the applied counts:

```bash
curl --fail-with-body --silent --show-error \
  -H 'Content-Type: application/json' --data-binary @local-data/watchlist.json \
  http://127.0.0.1:8000/api/watches/import/apply
umask 077
curl --fail --silent --show-error --output local-data/watchlist.export.json \
  http://127.0.0.1:8000/api/watches/export
```

All watch/group responses use `Cache-Control: no-store`; exports are attachments.
These APIs are private operator controls with no product login or public account
directory. Keep the current loopback development bindings; production network
privacy/access controls remain #17. Cross-origin access is not enabled. JSON-only
mutations prevent simple cross-origin form submissions from writing watches.
Do not publish personal exports or forward request bodies into logs.

## Verification

From the repository root in the devcontainer:

```bash
make lint test fixtures build
TEST_DATABASE_URL=postgresql://observer:observer-dev-only@db/wallet_observer \
  make test-integration
```

The integration target uses disposable per-test schemas. Default `make test`
skips database tests if TEST_DATABASE_URL is absent; those skips are not passes.
See [WO-005 acceptance evidence](acceptance/WO-005.md) for actual results and the
owner decision to defer the initial list to first-live setup.
