# Wallet Observer

Personal, read-only Solana wallet monitoring with a path to source-backed FOMO research.

**Website first:** the current target is a desktop-browser website. Native mobile apps, installable PWA features, device push, mobile-specific UX and mobile acceptance gates are deferred. Existing responsive behavior can remain. See the [scope decision](docs/decisions/0003-website-first.md).

**Current status: API, worker and frontend foundations run locally in fixture mode. PostgreSQL migrations and persistence primitives are implemented. Live collection and trade normalization remain future work.**

The [personal watchlist API](docs/watchlist-format.md) supports manual wallets,
aliases, notes, groups, pause/removal and atomic import/export. Collection intent
is saved locally; the collector and watchlist website UI remain later issues.

## Start here

Development setup: [docs/development.md](docs/development.md). Open the devcontainer, then run from the repository root:

```bash
make bootstrap
make doctor
make config-check
make migrate
make dev
```

Open <http://localhost:5173>. The default fixture mode uses local PostgreSQL and requires no provider or Telegram credentials. Ctrl-C stops API, worker and frontend together. Run `make lint test fixtures` for offline checks, or `make build` followed by `make api` to serve built assets at <http://localhost:8000>. See the [persistence and migration contract](docs/data-model.md) and [configuration contract](docs/configuration.md) for health and feature-flag behavior.

1. Read [BUILD_PLAN.md](BUILD_PLAN.md).
2. Follow the dependency order in [backlog/INDEX.md](backlog/INDEX.md).
3. Open the [development environment](docs/development.md), then read the [qualified source contract](docs/data-source-contract.md) from WO-002.
4. Complete the 18 first-live work items before the first personal beta.
5. Add the 10 expansion items only when their source and feature prerequisites are met.

## Included

- A full build plan covering scope, architecture, schema, APIs, recovery, UI, deployment, acceptance, and costs.
- 34 published issues (18 first-live, 10 expansion and 6 optional RayBot items) with why, what, how, expected files, dependencies, and definition of done.
- [AGENTS.md](AGENTS.md) for bounded AI-assisted implementation.
- [PUBLISHING.md](PUBLISHING.md) for creating the GitHub project and recording real issue links.
- [backlog/issues.json](backlog/issues.json) containing the published issue titles, bodies, and dependencies.

The [RayBot assessment](docs/raybot-integration-assessment.md) covers a possible secondary source using the existing paid plan. Its six optional issues start at [#34](https://github.com/nhattruong0204/wallet-observer/issues/34); live access remains unqualified and Helius remains the current source path.

## Stack

React/TypeScript, Python/FastAPI, one worker, PostgreSQL, Docker Compose, qualified Solana data, and one outbound Telegram chat.

## Scope

First live: 10–25 manual Solana wallets, supported trades, feed/history, wallet/token details, filters, private deployment, and recovery.

Expansion: observed positions, personal consensus, local rankings, saved settings, verified FOMO identities/theses/orders/clans, and selected additional chains.

Excluded: trade execution, unrelated social monitoring, pump.fun social calls, special monitors, audio, Bark, accounts/billing, and commercial/multi-user systems.

Provider keys, Telegram tokens, private watchlists, and raw private data must stay outside the repository.

## Budget and timing

Planning targets: first useful private deployment in roughly 5–10 focused working days after data access is proved; broader scope takes longer. Estimated first-live operations: USD 20–30/month on free data, or USD 70–80/month with the selected paid data tier, before model access and unknown FOMO/multi-chain feed costs. See the build plan for assumptions.

This is an independent implementation plan, not Wind source code or a claim about its private backend.

## GitHub

Repository: [nhattruong0204/wallet-observer](https://github.com/nhattruong0204/wallet-observer) (public, as created by the owner).

All [34 implementation issues](https://github.com/nhattruong0204/wallet-observer/issues) are published. See [WO-001 / #1](https://github.com/nhattruong0204/wallet-observer/issues/1) for the development environment and its [acceptance evidence](docs/acceptance/WO-001.md). The [backlog index](backlog/INDEX.md) links every issue; [github-issues.json](backlog/github-issues.json) records the actual issue numbers and URLs.
