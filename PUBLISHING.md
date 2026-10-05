# GitHub publication

Repository: [nhattruong0204/wallet-observer](https://github.com/nhattruong0204/wallet-observer).

## Current state

The owner created the repository as **public**. The default branch is **main**, issues are enabled, and the planning package and all 28 backlog issues are published. Issues #1–#4 are complete; the API, worker and website foundation run locally in fixture mode, with deliberate PostgreSQL migrations and persistence primitives. Live collection and the full monitoring product remain unimplemented.

The original Windows package was moved into `/home/truong/market_observer`. The pre-existing `build_plan.md` was preserved alongside the imported `BUILD_PLAN.md`.

All backlog work now targets the desktop-browser website first, with mobile work deferred under [decision 0003](docs/decisions/0003-website-first.md). Planning updates preserve issue states, dependency links and historical completion evidence.

## Published backlog

- [backlog/issues.json](backlog/issues.json) contains the complete published titles and bodies.
- [backlog/github-issues.json](backlog/github-issues.json) records actual GitHub numbers and URLs for all 28 stable WO identifiers.
- [backlog/INDEX.md](backlog/INDEX.md) links each issue and retains phase and dependency information.
- Issue bodies link dependencies to their actual GitHub issues while retaining WO identifiers. Issues were initially published open with unchecked definitions of done; their GitHub state now records implementation progress.

## Future updates

1. Read the current repository head and preserve unrelated changes. Do not force-push.
2. Use the recorded issue map to update existing issues. Before retrying any uncertain creation, search the exact `wallet-observer-task:WO-NNN` marker to avoid duplicates.
3. Keep issue bodies, local Markdown, payload JSON, and the index consistent when revising the backlog.
4. Verify file contents, issue titles/bodies, and dependency links after publication.

Provider credentials, bot tokens, personal watchlists, and raw private data must remain untracked.
