# Implementation backlog

34 prepared work items: **18 First live**, **10 Personal expansion**, **6 Optional RayBot**. All 34 GitHub issues are published; actual numbers and URLs are recorded in [github-issues.json](github-issues.json). GitHub issue state records progress; [WO-001 acceptance evidence](../docs/acceptance/WO-001.md) documents the development environment. [WO-004 acceptance evidence](../docs/acceptance/WO-004.md) records persistence, migration and recovery verification.

Read the [build plan](../BUILD_PLAN.md) and follow dependencies. WO IDs are stable planning IDs, not GitHub issue numbers.

| ID | Work item | Milestone | Dependencies |
|---|---|---|---|
| [WO-001](https://github.com/nhattruong0204/wallet-observer/issues/1) | Create the devcontainer and reproducible development toolchain | First live | None |
| [WO-002](https://github.com/nhattruong0204/wallet-observer/issues/2) | Qualify the Solana data source and capture representative fixtures | First live | WO-001 |
| [WO-003](https://github.com/nhattruong0204/wallet-observer/issues/3) | Bootstrap the API, worker, frontend, and configuration contract | First live | WO-001 |
| [WO-004](https://github.com/nhattruong0204/wallet-observer/issues/4) | Implement PostgreSQL migrations, canonical identities, and durable jobs | First live | WO-002, WO-003 |
| [WO-005](https://github.com/nhattruong0204/wallet-observer/issues/5) | Implement personal watchlists, aliases, groups, and bulk import | First live | WO-004 |
| [WO-006](https://github.com/nhattruong0204/wallet-observer/issues/6) | Build the provider adapter and live collection worker | First live | WO-002, WO-004, WO-005 |
| [WO-007](https://github.com/nhattruong0204/wallet-observer/issues/7) | Normalize swaps and reconcile transaction confirmation | First live | WO-004, WO-006 |
| [WO-008](https://github.com/nhattruong0204/wallet-observer/issues/8) | Implement durable recovery, bounded backfill, and gap reporting | First live | WO-004, WO-006, WO-007 |
| [WO-009](https://github.com/nhattruong0204/wallet-observer/issues/9) | Add token metadata, quote caching, and market-data provenance | First live | WO-002, WO-004, WO-007 |
| [WO-010](https://github.com/nhattruong0204/wallet-observer/issues/10) | Build feed, history, wallet/token queries, and search APIs | First live | WO-004, WO-005, WO-007, WO-009 |
| [WO-011](https://github.com/nhattruong0204/wallet-observer/issues/11) | Implement live updates with a committed replay cursor | First live | WO-004, WO-008, WO-010 |
| [WO-012](https://github.com/nhattruong0204/wallet-observer/issues/12) | Build the desktop website live feed and watchlist interface | First live | WO-005, WO-010, WO-011 |
| [WO-013](https://github.com/nhattruong0204/wallet-observer/issues/13) | Add wallet and token drill-down views | First live | WO-009, WO-010, WO-012 |
| [WO-014](https://github.com/nhattruong0204/wallet-observer/issues/14) | Deliver alerts to one Telegram chat with durable retries | First live | WO-004, WO-007, WO-009 |
| [WO-015](https://github.com/nhattruong0204/wallet-observer/issues/15) | Add CI and meaningful fixture-based regression gates | First live | WO-003, WO-004 |
| [WO-016](https://github.com/nhattruong0204/wallet-observer/issues/16) | Expose source health, usage budgets, and retention controls | First live | WO-006, WO-008, WO-009, WO-014 |
| [WO-017](https://github.com/nhattruong0204/wallet-observer/issues/17) | Prepare private VPS deployment, backups, and rollback | First live | WO-003, WO-004, WO-012, WO-014, WO-015, WO-016 |
| [WO-018](https://github.com/nhattruong0204/wallet-observer/issues/18) | Validate real traffic and release the first website beta | First live | WO-002, WO-005, WO-007, WO-008, WO-009, WO-010, WO-011, WO-012, WO-013, WO-014, WO-015, WO-016, WO-017 |
| [WO-019](https://github.com/nhattruong0204/wallet-observer/issues/19) | Add observed positions and first/add/re-entry/exit semantics | Personal expansion | WO-007, WO-008, WO-013, WO-018 |
| [WO-020](https://github.com/nhattruong0204/wallet-observer/issues/20) | Implement personal multi-wallet consensus signals | Personal expansion | WO-007, WO-008, WO-014, WO-016, WO-018 |
| [WO-021](https://github.com/nhattruong0204/wallet-observer/issues/21) | Build local rankings, mover history, and research summaries | Personal expansion | WO-009, WO-010, WO-018, WO-020 |
| [WO-022](https://github.com/nhattruong0204/wallet-observer/issues/22) | Add personal settings, saved views, and configuration portability | Personal expansion | WO-005, WO-012, WO-016, WO-018 |
| [WO-023](https://github.com/nhattruong0204/wallet-observer/issues/23) | Qualify FOMO identity, thesis, clan, and order data access | Personal expansion | WO-002, WO-018 |
| [WO-024](https://github.com/nhattruong0204/wallet-observer/issues/24) | Integrate verified FOMO identities and token theses | Personal expansion | WO-005, WO-010, WO-013, WO-023 |
| [WO-025](https://github.com/nhattruong0204/wallet-observer/issues/25) | Reconcile FOMO order attempts with on-chain executions | Personal expansion | WO-007, WO-008, WO-023, WO-024 |
| [WO-026](https://github.com/nhattruong0204/wallet-observer/issues/26) | Implement clan membership snapshots and resonance | Personal expansion | WO-020, WO-023, WO-024 |
| [WO-027](https://github.com/nhattruong0204/wallet-observer/issues/27) | Extend to selected additional chains through qualified adapters | Personal expansion | WO-002, WO-007, WO-008, WO-009, WO-018 |
| [WO-028](https://github.com/nhattruong0204/wallet-observer/issues/28) | Verify the expanded website release and complete the operator guide | Personal expansion | WO-018, WO-019, WO-020, WO-021, WO-022, WO-023; conditional: WO-024, WO-025, WO-026, WO-027 |

## Optional RayBot integration

Documentation feasibility is recorded in the [RayBot assessment](../docs/raybot-integration-assessment.md), with a [76-page review inventory](../docs/raybot-documentation-inventory.md). These six issues do not gate WO-018. Start with per-capability qualification; the owner reports Pro 200 but account access and available callback slots are unverified. Helius remains the qualified chain/recovery path.

| ID | Work item | Dependencies |
|---|---|---|
| [WO-029](https://github.com/nhattruong0204/wallet-observer/issues/34) | Qualify RayBot access, payload semantics, and delivery guarantees | WO-001, WO-002, WO-004 |
| [WO-030](https://github.com/nhattruong0204/wallet-observer/issues/35) | Import RayBot wallet lists into the personal watchlist | WO-005, WO-029 |
| [WO-031](https://github.com/nhattruong0204/wallet-observer/issues/36) | Persist authenticated RayBot webhooks with source health controls | WO-004, WO-006, WO-029 |
| [WO-032](https://github.com/nhattruong0204/wallet-observer/issues/37) | Reconcile RayBot observations with canonical Solana executions | WO-007, WO-008, WO-029, WO-031 |
| [WO-033](https://github.com/nhattruong0204/wallet-observer/issues/38) | Show qualified RayBot metadata and position observations on the website | WO-009, WO-013, WO-019, WO-029, WO-032 |
| [WO-034](https://github.com/nhattruong0204/wallet-observer/issues/39) | Compare RayBot Multi Wallet and Accumulation signals with local research | WO-020, WO-029, WO-031, WO-032 |

The RayBot FOMO username feature is recorded as a candidate in existing [WO-023 / #23](https://github.com/nhattruong0204/wallet-observer/issues/23); it does not qualify identities, theses, clans or off-chain order states.

## Website-first scope

Desktop-browser website delivery is the current target for all 34 issues. Native mobile apps, installable PWA features, device push, mobile-specific UX and mobile acceptance gates are deferred until an explicit future scope decision. Existing responsive behavior can remain; it does not create a mobile deliverable. Telegram alerts and the existing data/recovery gates remain in scope. See [decision 0003](../docs/decisions/0003-website-first.md).

## First-live boundary

WO-018 is the go-live gate. WO-019–WO-028 are expansion work and must not delay the wallet-first release. Source-dependent integrations can remain blocked with a written capability decision.

## Publication

Use [issues.json](issues.json) as the ready-to-publish payload and record actual issue numbers/URLs in [github-issues.json](github-issues.json). See [PUBLISHING.md](../PUBLISHING.md).
