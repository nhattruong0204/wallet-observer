# Wallet Observer

Personal, read-only Solana wallet monitoring with a path to source-backed FOMO research.

**Current status: planning package published; application not implemented.**

## Start here

1. Read [BUILD_PLAN.md](BUILD_PLAN.md).
2. Follow the dependency order in [backlog/INDEX.md](backlog/INDEX.md).
3. Implement [WO-001: devcontainer](backlog/issues/WO-001.md), then qualify the data source with WO-002.
4. Complete the 18 first-live work items before the first personal beta.
5. Add the 10 expansion items only when their source and feature prerequisites are met.

## Included

- A full build plan covering scope, architecture, schema, APIs, recovery, UI, deployment, acceptance, and costs.
- 28 published issues with why, what, how, expected files, dependencies, and definition of done.
- [AGENTS.md](AGENTS.md) for bounded AI-assisted implementation.
- [PUBLISHING.md](PUBLISHING.md) for creating the GitHub project and recording real issue links.
- [backlog/issues.json](backlog/issues.json) containing the published issue titles, bodies, and dependencies.

## Planned stack

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

All [28 implementation issues](https://github.com/nhattruong0204/wallet-observer/issues) are published and open. Start with [WO-001 / #1](https://github.com/nhattruong0204/wallet-observer/issues/1). The [backlog index](backlog/INDEX.md) links every issue; [github-issues.json](backlog/github-issues.json) records the actual issue numbers and URLs.
