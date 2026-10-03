# Solana source contract

Issue [#2 / WO-002](https://github.com/nhattruong0204/wallet-observer/issues/2).
Reviewed against official documentation and live mainnet responses on 2026-10-03.
This qualifies source inputs for later implementation; no production collector or
trade normalizer is implemented here. Read the [decision](decisions/0001-solana-source.md)
and [experiment evidence](acceptance/WO-002.md) before enabling a capability.

## Transport and authentication

The candidate is Helius Parsed Streams with Parsed Events history. A user-owned
Free-plan key successfully authenticated both services. The probe reads
`HELIUS_API_KEY` from the environment or ignored `.env`; it never passes a key on
the command line. No wallet signing key is needed.

| Purpose                                 | Interface                                                                  | Authentication                                                     |
| --------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Live decoded input                      | `wss://beta.helius-rpc.com/`, JSON-RPC `parsedTransactionSubscribe`        | `x-api-key` handshake header                                       |
| Historical decoded input                | `POST https://mainnet.helius-rpc.com/v1/parsed-events/transaction-history` | `api-key` query parameter                                          |
| Signature lookup                        | `POST https://mainnet.helius-rpc.com/v1/parsed-events/transactions`        | `api-key` query parameter; documented, not exercised in this trial |
| Reference signatures, slots, block time | `POST https://mainnet.helius-rpc.com/`, standard Solana JSON-RPC           | `api-key` query parameter                                          |

Do not log URLs, handshake headers, response bodies, watchlists, or exception
strings from networking libraries. Raw captures are mode 0600 under ignored
`local-data/qualification/`; run directories are mode 0700. HTTP redirects are
refused. WebSocket diagnostic logging is disabled in the probe.

References: [stream protocol](https://www.helius.dev/docs/parsed-streams/quickstart),
[Parsed Events requests](https://www.helius.dev/docs/parsed-events/quickstart).

## Filtering and coverage

The exercised subscription uses one `accounts.include` list, `includeFailed: true`,
`includeCpi: true`, and options `commitment: confirmed`, `details: full`. A numeric
subscription acknowledgement is required. Both connections were authenticated
independently; subscription IDs are local to a connection.

`accounts.include` tests instruction accounts, including undecoded instructions.
It does not automatically expand a wallet into owned token accounts. Program ID
is separate from the instruction account list. A transaction may match because
the watched account participates in account creation or a fee path; this does
not make it the trader. One observed notification matched an
`associated_token_account.create_idempotent` instruction, which was verified
against the private watchlist.

Incoming SPL transfers whose owner appears only in token balance metadata can
be absent from an owner-address subscription. Historical RPC address lookup has
a related account-key limitation. Complete owner coverage, newly created or
closed token accounts, and historical owner relationships are **not qualified**.
The future collector must expose partial coverage and independently qualify
any token-account expansion. Do not silently claim whole-wallet history.

## Payload and execution semantics

Live notification: `params.result.context.slot` plus `value.transaction`,
`value.instructions`, and `value.matchedIndexes`. The real capture has transaction
signature, fee payer, integer lamport fee, account keys, summary, transfers,
`status: ok`, and `blockTime: null`. `matchedIndexes` selects instruction-array
positions; it is not a durable execution identity.

History returns `data` and optional `paginationToken`. Each result has `signature`,
`parserStatus`, `parsed`, and (when requested) `rawTransaction`. Parser success is
separate from execution success: the captured failed transaction has
`parserStatus: OK`, `parsed.transactionStatus: ERROR`, and a non-null raw
`meta.err`. A failed transaction can still contain decoded attempted transfers
and swap instructions. It produces no successful trade.

| Field or fact               | Rule for downstream work                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Transaction identity        | `(solana, signature)`; preserve case                                                                           |
| Instruction identity        | Transaction identity plus `instructionIndex` and nullable `innerInstructionIndex`; retain `stackHeight`        |
| Actor                       | Verify decoded authority/user roles and owner balance changes; fee payer or filter match alone is insufficient |
| Token identity              | `(solana, mint)`; preserve original address case in runtime data                                               |
| Amounts                     | Preserve raw integer/string quantities and decimal counts; never use binary floating point for amounts         |
| Summary amounts             | Venue amounts can differ from owner debits because of fees; validate against raw pre/post balances             |
| Transfers                   | A credit without a supported execution is a transfer, not a buy                                                |
| Unknown instructions/routes | Preserve evidence and classify unknown; do not infer missing legs                                              |
| Native SOL / WSOL           | Account funding, rent, wrapped token movement and closure are separate effects                                 |
| Confirmation                | Observed under a confirmed subscription/request; finalization requires separate reconciliation                 |
| Order outcome               | Not supplied by on-chain confirmation; leave source order status null                                          |
| Positions/valuation         | Opening history, USD prices and complete economic positions are not established by this feed                   |

The buy fixture's owner debit is **70000000** raw WSOL while its venue summary
input is **69306930**. The routed example similarly reports **7467384113** input
while the watched owner loses **7500000000**. These real differences prohibit
copying summary amounts directly into a wallet ledger.

References: [parsed response fields](https://www.helius.dev/docs/parsed-events/parsed-response),
[Solana transaction metadata](https://solana.com/docs/rpc/http/gettransaction).

## Program support

The trial includes decoded `system`, `token`, `token_2022`,
`associated_token_account`, `compute_budget`, `pump_amm`, `swap_orchestrator`,
`lb_clmm`, Jupiter and OKX router instructions. This is observed decoder coverage,
not an application support promise. The committed cases deliberately preserve
an undecoded `bison_fi` route leg and `pump_fees` instructions.

| Execution candidate                                                      | Evidence and release constraint                                                                                                                  |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| PumpSwap buy/sell, program `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | Real successful buy and sell, decoded user role, raw owner deltas. Normalizer must still handle fees/Token-2022 and incidental watched accounts. |
| Ordinary SPL transfer                                                    | Real +1000 raw-unit owner credit with no swap; retain transfer semantics.                                                                        |
| DFlow multi-leg route                                                    | Real three-leg route, transient WSOL account and an undecoded leg; economic classification remains `unknown.swap`.                               |
| Other decoder catalog programs                                           | Documentation or unreviewed history only; no production trade support inferred.                                                                  |

The runtime decoder catalog can change. Optional future discovery with
`describeProgram` uses its separately documented `fs-beta.helius-rpc.com`
connection; that discovery endpoint was not exercised. Do not invent role names
or assume every IDL-decoded instruction represents an execution.

## Recovery and deduplication

Parsed Streams offers **at-most-once live delivery without replay**. On reconnect,
resubscribe and backfill from the last durably committed slot, including overlap.
Include the boundary slot itself: more than one transaction can share it.
The probe uses a 32-slot overlap for the experiment; it is not a proven retention
or maximum-outage bound.

The exercised history request sets `address`, `limit: 100`, `sortOrder: desc`,
`commitment: confirmed`, `includeRawTransaction: true`, and inclusive
`slot: {gte, lte}`. Follow returned `paginationToken` with the same bounds. Missing
token ends the available page range; it does not prove ownership completeness.
The probe caps history at two pages per address per phase, rejects repeated
cursors, and reports an explicit incomplete result when the cap is reached.

Compare recovered successful parser results against
`getSignaturesForAddress` in the same slot interval, including failed executions.
The RPC reference is separately queried from the same provider, not an independent
validator. Its 1000-result bound must reach below the lower slot before it can
support coverage. The future collector needs durable raw writes and checkpoints
in one transaction; overlap must upsert by signature and must not repeat alerts.
WO-006 implements persistence; this probe does not simulate a production database.

The overlap fixture contains two **actual** deliveries of one signature: live
notification and history response after reconnect. This proves an observable
duplicate input path. It does not claim a duplicate was spontaneously sent twice
on the live connection.

Retention length, long-outage completeness, finalized/reorg correction, and
token-owner expansion remain unqualified. A parser error, truncated pagination,
or missing reference signature must leave a visible coverage gap.

References: [Helius reconnect behavior](https://www.helius.dev/docs/parsed-streams/guides/handling-reconnects),
[history request bounds](https://www.helius.dev/docs/parsed-events/quickstart),
[RPC reference semantics](https://solana.com/docs/rpc/http/getsignaturesforaddress).

## Rate, credit and latency budget

The documented Free plan has 1 million included monthly credits, 10 standard RPC
requests/second and 2 Enhanced/DAS requests/second. Parsed Streams is available
on Free, with 5 connections per project and 25 subscriptions per connection.
The probe uses one connection at a time and paces HTTP requests at least 0.6
seconds apart. Subscription client traffic is limited to 10 messages/second;
account include lists permit up to 100 entries. This trial uses two addresses.

Documented charges: 1 credit per delivered stream event, 10 per Parsed Events
request, 1 per exercised standard RPC request. Requests with 100 historical
results still count as requests, not 100 Parsed Events charges. This is the new
Parsed Events API, not legacy Enhanced Transactions pricing.

Each opt-in run has a **500-credit client accounting ceiling**, at most 200
received events (default 100), two connection windows of at most 150 seconds,
and an intentional outage of at most 300 seconds. HTTP response size and timeout
are bounded; the probe has no automatic HTTP retries. Server deliveries queued
before closure may be billed without being consumed. The local ceiling is not
a provider-side spending cap. No purchase, upgrade or overage was authorized.

The acceptance record reports actual request/event counts and credits estimated
from these published rates. Provider dashboard billing totals were not available
to the probe and are not presented as measured invoices.

Stream `blockTime` is null in the captured payload. Delay is computed by fetching
`getBlockTime(context.slot)` and subtracting that block estimate from client UTC
receipt time. This includes chain confirmation, transport and clock error; it is
not isolated provider latency. Missing block time remains unavailable. Small
samples cannot establish percentile performance or an SLA.

References: [plans](https://www.helius.dev/docs/billing/plans),
[credits](https://www.helius.dev/docs/billing/credits),
[rate limits](https://www.helius.dev/docs/billing/rate-limits),
[Solana block-time estimate](https://solana.com/docs/rpc/http/getblocktime).

## Failure handling

| Failure                          | Required response                                                     |
| -------------------------------- | --------------------------------------------------------------------- |
| HTTP 401 / invalid credentials   | Stop and correct local configuration; never echo the key or URL       |
| HTTP 429 / capacity exhausted    | Stop this bounded trial; production backoff must respect the plan     |
| JSON-RPC -32602 or -32000        | Invalid parameters/filter limits; fix request, do not retry unchanged |
| JSON-RPC -32001 / -32002         | Transient service/rate error; bounded retry with jitter in production |
| Connection loss / server restart | Reconnect, resubscribe, backfill; subscription ID does not survive    |
| Slow-consumer close 1008         | Narrow input or improve processing; recover missing interval          |
| Quiet connection close 1000      | May be the documented 10-minute idle timeout; recover after reconnect |
| Unknown shape / parser failure   | Preserve private evidence, stop qualification and report a gap        |
| Cursor repetition / page cap     | Never advance a complete-coverage checkpoint                          |

These failure codes are documented behavior. Offline tests exercise error
redaction, bounds and pagination; the trial did not deliberately provoke rate
limits or invalid-auth responses. No retries or success measurements are invented.

## Unavailable product data

FOMO identity verification, theses, clans, off-chain orders, refunds, global
holdings and source order outcomes are unavailable here and remain disabled
pending WO-023. No Wind endpoint is used. No personal identity is inferred from
the supplied wallets. Quotes and USD valuation require their own qualified source.
