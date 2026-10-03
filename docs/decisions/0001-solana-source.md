# 0001: Helius Parsed Streams with bounded Parsed Events recovery

Date: 2026-10-03. Status: accepted for a limited wallet-first implementation.
Issue: [#2 / WO-002](https://github.com/nhattruong0204/wallet-observer/issues/2).

## Decision

Use Helius Parsed Streams at confirmed commitment as the primary live source,
with Parsed Events address history for bounded recovery and standard Solana RPC
for reference signatures and block-time estimates. Keep integration server-side.
The user's existing Free plan authenticated both services without an upgrade.

**GO** for building the wallet-first collector and normalizer against the
[source contract](../data-source-contract.md) and sanitized real fixtures.
This is permission to implement the qualified path, not a claim that an app or
production ingestion service already runs.

## Evidence

Two user-supplied wallets were tested. Historical sampling returned 227 records
per run, with a two-page cap on the busier address. Reviewed fixtures cover buy,
sell, ordinary transfer, failed execution, multi-leg routing, temporary wrapped
SOL, overlapping delivery, and an unsupported route.

The first run received one live notification and recovered its signature again
from history after reconnect. The second deliberately disconnected for 300
seconds. One transaction in that interval appeared in RPC reference signatures
and was recovered by the bounded history request; it was absent from the live
capture. The other wallet had no traffic during either recovery interval.

The first notification arrived 1.362 seconds after its RPC block-time estimate.
There is no statistically useful latency distribution. Across the two runs,
27 HTTP requests and one consumed notification correspond to 154 estimated
credits at the documented rates. Provider invoice/dashboard deltas were not
available. Exact intervals and results are in the [acceptance record](../acceptance/WO-002.md).

## Conditions and disabled capabilities

- Owner-address filtering covers instruction participation, not every owned
  token account. Expose partial coverage; complete wallet balances/history are
  not established.
- Attribute a trade to the decoded actor only after checking owner balance
  changes. The direct buy/sell fixtures include an incidental watched address
  that must not be labeled as the trader.
- Venue summary input can exclude fees. Use exact raw values and retain unknown
  economic cases until the normalizer supports them.
- The DFlow example includes an undecoded leg. Store it as unknown; do not enable
  automatic trade alerts/statistics for that route merely because a swap summary exists.
- Confirmed is not finalized. Reorg correction and finalization are later work.
- Recovery is proven for one nonempty five-minute sample, not arbitrary outages.
  Truncated pagination, parser failures and missing history must produce gaps.
- FOMO identities, theses, clans and off-chain order states are unavailable and
  remain disabled pending WO-023. Valuation and complete P&L need separate sources.

## Alternatives and consequences

An owner-only stream cannot provide complete token ownership history. Building
an indexer now would expand scope before a measured need; instead retain honest
coverage state and qualify any expansion later. The legacy Enhanced Transactions
API has a different response model and credit schedule; this trial uses the new
Parsed Events interface. No second provider, new infrastructure, paid plan,
trading capability or runtime AI dependency is introduced.

The collector must implement idempotent persistence, safe checkpoints and
overlap recovery. Its acceptance tests can use these real inputs, but the
offline fixture checks in WO-002 do not stand in for production recovery tests.
