# Implementation instructions

## Read first

Read BUILD_PLAN.md, backlog/INDEX.md, the current issue body, and any existing source contracts before changing code. The repository begins as a planning package; do not claim the app runs before it is implemented.

## Working method

- Implement one bounded issue at a time. Respect its dependencies and source qualification gates.
- Preserve the explicit exclusions in BUILD_PLAN.md. Do not add execution, private-key handling, commercial features, or extra platforms.
- Add the devcontainer before application implementation. Pin selected toolchains and lock dependencies.
- Inspect existing files before modifying them. Keep unrelated work intact.
- Prefer one API service, one worker and PostgreSQL. Add infrastructure only to resolve a measured limitation.
- Use official provider documentation and sanitized real fixtures. Never invent supported payloads or integrations.
- Keep provider credentials, bot tokens, personal watchlists and raw private data untracked and out of logs/frontend bundles.
- Preserve Solana address case; use chain/address token identity and exact decimal/integer amounts.
- Distinguish transfer, execution, source order status, chain confirmation, and observed position completeness.
- Make ingestion/recovery idempotent. Persist checkpoints safely and use a committed delivery cursor.
- Use meaningful correctness/recovery tests and deterministic fixtures. Paid live probes are explicit and bounded.
- Keep setup/deploy commands in documentation executable and current.
- Record source-blocked capabilities as blocked or disabled; do not silently fabricate data or mark them shipped.
- When finishing an issue, report changed behavior, verification evidence, limitations, and the definition-of-done checklist.

## Scope and spending

Monitoring is read-only. No trading wallet or signing keys are required. Runtime AI is not a baseline dependency. A plan mentioning a vendor does not itself authorize a purchase or a subscription upgrade.

## Branches and review

Use a small implementation branch/PR per issue when GitHub is available. Reference the actual issue number after publication; WO identifiers are stable planning IDs. Do not invent checks, measurements, issue IDs, or deployment success.

