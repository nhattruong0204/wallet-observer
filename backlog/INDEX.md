# Implementation backlog

28 prepared work items: **18 First live**, **10 Personal expansion**. These are issue drafts; no GitHub issue numbers have been assigned.

Read the [build plan](../BUILD_PLAN.md) and follow dependencies. WO IDs are stable planning IDs, not GitHub issue numbers.

| ID | Work item | Milestone | Dependencies |
|---|---|---|---|
| [WO-001](issues/WO-001.md) | Create the devcontainer and reproducible development toolchain | First live | None |
| [WO-002](issues/WO-002.md) | Qualify the Solana data source and capture representative fixtures | First live | WO-001 |
| [WO-003](issues/WO-003.md) | Bootstrap the API, worker, frontend, and configuration contract | First live | WO-001 |
| [WO-004](issues/WO-004.md) | Implement PostgreSQL migrations, canonical identities, and durable jobs | First live | WO-002, WO-003 |
| [WO-005](issues/WO-005.md) | Implement personal watchlists, aliases, groups, and bulk import | First live | WO-004 |
| [WO-006](issues/WO-006.md) | Build the provider adapter and live collection worker | First live | WO-002, WO-004, WO-005 |
| [WO-007](issues/WO-007.md) | Normalize swaps and reconcile transaction confirmation | First live | WO-004, WO-006 |
| [WO-008](issues/WO-008.md) | Implement durable recovery, bounded backfill, and gap reporting | First live | WO-004, WO-006, WO-007 |
| [WO-009](issues/WO-009.md) | Add token metadata, quote caching, and market-data provenance | First live | WO-002, WO-004, WO-007 |
| [WO-010](issues/WO-010.md) | Build feed, history, wallet/token queries, and search APIs | First live | WO-004, WO-005, WO-007, WO-009 |
| [WO-011](issues/WO-011.md) | Implement live updates with a committed replay cursor | First live | WO-004, WO-008, WO-010 |
| [WO-012](issues/WO-012.md) | Build the responsive live feed and watchlist interface | First live | WO-005, WO-010, WO-011 |
| [WO-013](issues/WO-013.md) | Add wallet and token drill-down views | First live | WO-009, WO-010, WO-012 |
| [WO-014](issues/WO-014.md) | Deliver alerts to one Telegram chat with durable retries | First live | WO-004, WO-007, WO-009 |
| [WO-015](issues/WO-015.md) | Add CI and meaningful fixture-based regression gates | First live | WO-003, WO-004 |
| [WO-016](issues/WO-016.md) | Expose source health, usage budgets, and retention controls | First live | WO-006, WO-008, WO-009, WO-014 |
| [WO-017](issues/WO-017.md) | Prepare private VPS deployment, backups, and rollback | First live | WO-003, WO-004, WO-012, WO-014, WO-015, WO-016 |
| [WO-018](issues/WO-018.md) | Validate real traffic and release the first personal beta | First live | WO-002, WO-005, WO-007, WO-008, WO-009, WO-010, WO-011, WO-012, WO-013, WO-014, WO-015, WO-016, WO-017 |
| [WO-019](issues/WO-019.md) | Add observed positions and first/add/re-entry/exit semantics | Personal expansion | WO-007, WO-008, WO-013, WO-018 |
| [WO-020](issues/WO-020.md) | Implement personal multi-wallet consensus signals | Personal expansion | WO-007, WO-008, WO-014, WO-016, WO-018 |
| [WO-021](issues/WO-021.md) | Build local rankings, mover history, and research summaries | Personal expansion | WO-009, WO-010, WO-018, WO-020 |
| [WO-022](issues/WO-022.md) | Add personal settings, saved views, and configuration portability | Personal expansion | WO-005, WO-012, WO-016, WO-018 |
| [WO-023](issues/WO-023.md) | Qualify FOMO identity, thesis, clan, and order data access | Personal expansion | WO-002, WO-018 |
| [WO-024](issues/WO-024.md) | Integrate verified FOMO identities and token theses | Personal expansion | WO-005, WO-010, WO-013, WO-023 |
| [WO-025](issues/WO-025.md) | Reconcile FOMO order attempts with on-chain executions | Personal expansion | WO-007, WO-008, WO-023, WO-024 |
| [WO-026](issues/WO-026.md) | Implement clan membership snapshots and resonance | Personal expansion | WO-020, WO-023, WO-024 |
| [WO-027](issues/WO-027.md) | Extend to selected additional chains through qualified adapters | Personal expansion | WO-002, WO-007, WO-008, WO-009, WO-018 |
| [WO-028](issues/WO-028.md) | Verify the expanded personal release and complete the operator guide | Personal expansion | WO-018, WO-019, WO-020, WO-021, WO-022, WO-023; conditional: WO-024, WO-025, WO-026, WO-027 |

## First-live boundary

WO-018 is the go-live gate. WO-019–WO-028 are expansion work and must not delay the wallet-first release. Source-dependent integrations can remain blocked with a written capability decision.

## Publication

Use [issues.json](issues.json) as the ready-to-publish payload and record actual issue numbers/URLs in [github-issues.json](github-issues.json). See [PUBLISHING.md](../PUBLISHING.md).
