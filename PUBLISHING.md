# Publish this prepared project

Target: **nhattruong0204/wallet-observer**, private, issues enabled, default branch main.

## Current state

The owner was verified through the GitHub plugin as nhattruong0204. The plugin exposes file/issue operations, but no repository-creation operation. No repository, branch, commit, or issue has been created for this project yet.

## Repository creation

Use the GitHub browser UI after the required browser-fallback permission, or have the owner create the empty repository. Default to private for this personal project. Initialize a README if convenient. Do not modify launchradar, market-sidekick, or another existing repository as a substitute.

A user-run GitHub CLI alternative, if the user has gh installed and authenticated locally:

```bash
gh repo create nhattruong0204/wallet-observer --private --description "Personal read-only wallet monitoring and source-backed FOMO research" --add-readme
```

Repository creation is not a purchase. GitHub App access to the new repository must be available before publishing files/issues.

## File publication

1. Fetch the repository metadata and current default-branch head.
2. Publish README.md, BUILD_PLAN.md, AGENTS.md, this file, .gitignore, and backlog/ files.
3. Use the current tree/head when composing a commit. Do not force-push unrelated changes.
4. Update pending-publication language after the repository and issues actually exist.
5. Verify the resulting file content and default-branch commit.

## Issue publication

- Source of truth: backlog/issues.json.
- Create 28 issues using each entry's complete title and body. Do not mark them completed.
- Retain the WO ID in the title. Do not assume a WO numeric suffix equals the GitHub issue number.
- After each successful create, record the actual number and URL in backlog/github-issues.json.
- On partial failure or uncertain acknowledgment, search by the exact WO marker before retrying to avoid duplicates.
- Once all issues exist, replace dependency WO markers in issue bodies with actual issue links while retaining the stable IDs.
- Add actual links to backlog/INDEX.md and README.md.
- Labels/milestones may be added if available, but title/phase/dependency content already provides grouping. Do not block publication on cosmetic metadata.

## Verification

Confirm repository visibility, default branch, plan contents, all 28 issue titles/bodies, the dependency map, and that every issue includes why, what, how, and definition of done.

Only then report the repository and issue links as created.

