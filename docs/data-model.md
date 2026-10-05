# Persistence and migration contract

Implemented for [issue #4 / WO-004](https://github.com/nhattruong0204/wallet-observer/issues/4).
This is a PostgreSQL storage foundation for the desktop website. It does not
implement a provider collector, a trade normalizer, a watchlist API, live browser
transport or Telegram sending. Those remain their own issues and source gates.

## Schema and identity

| Tables                                                 | Contract                                                                                                                                                                                                        |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `wallets`, `tokens`                                    | Unique `(chain, address)` with case-sensitive `C` collation. Composite foreign keys prevent cross-chain joins. Token metadata may be unknown.                                                                   |
| `watches`, `watch_groups`, `watch_group_members`       | One watch per wallet, manual alias/note, explicit monitoring state and group membership. No product accounts.                                                                                                   |
| `source_identities`, `identity_wallet_links`           | Source identifiers and evidence-bearing links, separate from manual watch labels. No FOMO source is enabled by creating these tables.                                                                           |
| `raw_source_events`, `source_payloads`                 | One deduplication envelope per `(provider, chain, source_event_id)`. Distinct payload hashes retain stream/history/correction variants; identical retries reuse a payload.                                      |
| `canonical_events`, `event_sources`                    | Stable UUID and unique `(chain, transaction_id, instruction_index, inner_instruction_index, wallet_id)`. Root instruction NULL and inner instruction zero are distinct. Multiple sources can support one event. |
| `event_revisions`                                      | Contiguous, immutable revision snapshots. Kind, chain confirmation, source order status and coverage remain separate. Corrections append; they do not rewrite delivered history.                                |
| `executions`, `execution_legs`                         | Current execution state belongs to one canonical event; ordered legs reference chain-scoped tokens. Previous states remain in revision snapshots.                                                               |
| `token_quotes`                                         | Source/time-specific prices with explicit availability and expiry. Current quotes are separate from execution USD values.                                                                                       |
| `source_checkpoints`, `coverage_gaps`                  | Versioned safe slot/cursor per provider/chain/scope and explicit gap intervals. A checkpoint is not proof of complete owner coverage.                                                                           |
| `durable_jobs`                                         | Unique work intent `(kind, object_key)`, bounded attempts, retry time, expiring lease and fresh ownership token per attempt.                                                                                    |
| `publication_outbox`, `delivery_state`, `delivery_log` | Transactional revision intent followed by serialized, committed replay positions. Producer sequence IDs are never client cursors.                                                                               |
| `notification_outbox`                                  | Unique event/destination intent referencing a durable job, expiry and eventual message ID. It contains no bot credential and does not send anything.                                                            |
| `schema_migrations`                                    | Applied version, filename, SHA-256 and application time.                                                                                                                                                        |

There are no user, billing, entitlement, quota or session tables. Positions,
signals, FOMO metadata and settings APIs remain later features. Chain identifiers
in the schema do not enable adapters for additional chains.

Exact raw amounts use an unconstrained PostgreSQL `numeric` domain with explicit
integer, nonnegative and 78-digit bounds. A fractional input is rejected rather
than rounded as it would be by a fixed-scale integer column. Valuations use exact,
finite, nonnegative decimals; unavailable values remain NULL. Python storage
inputs reject float amounts and serialize exact amounts as JSON strings.
Equivalent decimal encodings have one canonical fingerprint without using
context-dependent decimal rounding. Timestamps use `timestamptz`; supplied event
times must include a timezone and are normalized to UTC. Missing occurrence times
remain NULL.

The storage layer preserves address case; chain-specific address validation and
normalization belong to the watch/provider adapters. Sanitized fixture aliases
are intentionally accepted by storage tests and are never queried on chain.

## Transaction boundary

Use `async with transaction(settings) as store:` from
`wallet_observer.db`. Every method participates in that connection's transaction;
none commits independently. The context commits on successful exit and rolls
back on exceptions or connection loss. Let `RevisionConflict`,
`CheckpointConflict` and database errors escape the context before retrying the
whole bounded batch. Do not catch a write error and continue committing other
parts of the same logical batch.

A future ingestion batch should:

1. Store each source envelope and payload; enqueue required processing work.
2. If a qualified canonical result is available, call `write_event` with the
   expected current revision. A matching content fingerprint is an idempotent
   no-op, including replay of the same event through another transport.
3. Advance the checkpoint with its expected version only after all records and
   required work in the safe boundary have been persisted in this transaction.
4. Exit the context successfully. Only then may downstream delivery read it.

Checkpoint compare-and-swap rejects stale versions and slot regression. The
collector must still establish a genuinely safe boundary, persist gap records
and honor bounded source history. Storage cannot infer missing provider events.

A trigger writes publication intent in the same transaction as each revision
and advances the current revision only by one. Database constraints preserve
identity even if multiple writers race. An exact old replay does not increment
the revision; a conflicting correction must re-read the current version.
Replay provenance does not itself change economic identity. Replayed events
retain their initial replay flag in the snapshot so later notification policy
can suppress historical delivery.

`CanonicalEvent` accepts only an explicit storage contract, not arbitrary provider
JSON. A trade requires successful execution input/output legs; a transfer,
unknown route or failed event cannot claim a successful trade execution. This
validation does not qualify a new route. A correction that removes execution
semantics marks an existing execution reverted. Downstream aggregates must check
current execution status, chain confirmation and coverage rather than counting
all historical revision rows.

Raw payloads default to seven days' retention, bounded to 1–90 days per write.
`expire_payloads(limit=...)` deletes at most 1,000 expired payloads per transaction.
Deduplication envelopes and canonical facts survive payload deletion. Automatic
retention scheduling and storage/usage controls belong to #16; this issue
provides the expiry field and bounded deletion primitive, not a running janitor.

## Committed delivery cursor

`dispatch_batch(settings, limit=100)` uses its own transaction after producers
commit. A row lock on the singleton `delivery_state` serializes dispatchers. It
selects visible, undispatched outbox rows, writes their immutable snapshots with
contiguous delivery positions, marks intent dispatched and updates the watermark
in the same transaction. The function returns only after that commit.

| Producer order                                | What the dispatcher does                                   |
| --------------------------------------------- | ---------------------------------------------------------- |
| A allocates outbox ID 1 but has not committed | A is invisible to dispatch.                                |
| B allocates ID 2 and commits first            | B is published at delivery position 1.                     |
| A commits later                               | A remains pending and is published at delivery position 2. |
| A rolls back instead                          | No A event or delivery is published.                       |

The dispatcher always queries pending rows; it never filters producers by
`outbox.id > last_seen_id`. Rollback of a dispatch also rolls back its positions,
watermark and dispatched flags. Concurrent dispatch calls serialize on the same
state row, so a later position cannot become visible before an earlier one.

`read_delivery` reads a page and watermark in one statement snapshot. Continue
from `next_cursor`, the last returned position, **not** from `committed_position`
when a page is truncated. Empty pages retain the requested cursor. A future
cursor is rejected. Replay retention/resnapshot and WebSocket protocol are #11;
this version does not delete delivery history. No background dispatcher or
browser transport is enabled by the foundation worker yet.

## Durable jobs

Enqueue work in the same transaction as its source facts. Claim work in a short
separate transaction using `FOR UPDATE SKIP LOCKED`; commit that claim before
performing external work. A claim increments attempts and issues a fresh UUID
lease token. Lease duration is bounded to 0.1–300 seconds and attempts to 1–20.

`finish` requires the same still-unexpired token. An old worker cannot acknowledge
or reschedule a job claimed by another worker, even if it resumes later. Failed
work waits a bounded retry interval (0–3,600 seconds). An expired final attempt
becomes terminal `failed` on a later claim pass; it cannot remain running forever.
Errors are static lowercase codes, never exception text or credential URLs.
Split long work into bounded jobs; lease renewal is not implemented here.

An enqueue retry reuses the first intent and never replaces its payload. Use a
revision-bearing object key when a genuinely new operation is needed. These are
at-least-once work primitives: handlers still need idempotent writes, and external
Telegram acknowledgement uncertainty remains #14. No exactly-once external send
guarantee is implied. Job handlers and worker scheduling are later work.

## Migrations and upgrade procedure

The existing pinned Psycopg 3 dependency executes ordered SQL files; there is no
new ORM or migration dependency. `0001_canonical.sql` creates identity/source/
canonical storage. `0002_durable_delivery.sql` adds work leases, notifications,
revision triggers and the delivery cursor, including publication intent for any
existing v1 revision snapshots. SQL files are included in the backend wheel and
source distribution.

From the repository root inside the devcontainer:

```bash
make bootstrap
make doctor
make config-check
make migrate
```

The command uses private `DATABASE_URL` configuration, applies all pending files
atomically under an advisory transaction lock, and is safe to repeat. Applied
filenames/checksums must match this release. A changed, missing or unknown applied
migration fails; never edit a migration already used by another deployment. Add
one new sequential file instead. DDL errors roll back all pending files and their
version records together. Concurrent migration attempts serialize. Connection,
lock and statement timeouts bound failures; the CLI emits redacted lifecycle
logs and exits 1 on migration failure, 2 on invalid configuration.

For a future upgrade, stop API/worker writers, record the current release, make
and verify a private backup, deploy the matching code/SQL release, run
`make migrate`, then restart and verify services. The migrations are deliberately
forward-only. There is no automatic destructive downgrade. If an upgrade cannot
be corrected forward, restore a verified backup into a separate database and run
the matching previous release. Production backup/restore automation remains #17.

For the local development database, the container's PG variables support an
explicit private backup without putting a password in command arguments:

```bash
umask 077
mkdir -p local-data/backups
pg_dump --format=custom --file=local-data/backups/before-migration.dump
psql --no-psqlrc --command='SELECT version, name, applied_at FROM schema_migrations ORDER BY version;'
```

The application does not run migrations implicitly on startup. Current health
endpoints still check database connectivity for the foundation services; they do
not certify the schema version or collector readiness. Inspect the migration
result deliberately before using persistence APIs.

## Verification

Default `make test` runs without a database; integration tests skip unless
`TEST_DATABASE_URL` is explicitly set. To run the required persistence checks in
the devcontainer against its disposable development database:

```bash
TEST_DATABASE_URL=postgresql://observer:observer-dev-only@db/wallet_observer make test-integration
```

The credentials above are the committed development-only defaults. Never point
this command at production. Each test creates a random `wo004_test_*` schema and
removes only that schema; it does not truncate application tables. The target
fails with a clear message if `TEST_DATABASE_URL` is absent. Provider/Telegram
credentials are not used.

Tests use the sanitized real buy and stream/history-overlap captures from #2.
The buy storage DTO uses the reviewed owner's balance deltas (including fees),
not the unrelated watched account or the venue's net input summary. Separate
controlled canonical identity/precision variants test database invariants; they
are not represented as additional provider captures or route qualification.

Primary references: [PostgreSQL transaction locks](https://www.postgresql.org/docs/16/explicit-locking.html),
[PostgreSQL row selection and SKIP LOCKED](https://www.postgresql.org/docs/16/sql-select.html),
and [Psycopg transaction contexts](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).
