# Decision 0003: deliver the website first

Status: accepted at the owner's request; recorded on 2026-10-05.

## Decision

The current product target is a desktop-browser website backed by the existing
API, worker and PostgreSQL architecture. Complete the first-live website before
the planned website expansion. Both milestones exclude mobile delivery unless
the owner explicitly brings it back into scope.

Deferred work includes:

- Native iOS/Android applications, mobile frameworks and app-store packaging.
- Installable PWA and offline-app features, device push and mobile background tasks.
- Mobile-specific navigation, touch interactions, layouts and device settings.
- Mobile-device test matrices and mobile-width release acceptance requirements.

The backlog previously required roughly 390px browser layouts; it did not contain
a native mobile application implementation issue. Remove that layout requirement
from the current delivery gates and make the mobile deferral explicit in every
issue. Do not invent or close a mobile issue as completed.

## Retained website scope

Keep the website feed, watchlist, settings, wallet/token pages, desktop mouse and
keyboard access, and readable loading, empty, stale, error and offline states.
Browser reconnect and server-side collection/recovery remain required. Offline
status reporting does not require an offline-capable app.

One outbound Telegram bot/chat remains part of the server-side alerting scope;
it does not require a Wallet Observer mobile app. Data qualification, exact
amounts, source gates, private access, backups and all existing safety exclusions
remain in force. This decision does not add trading, account systems or spending.

Existing responsive CSS and the small-viewport browser check from issue #3 may
remain as incidental coverage. No new mobile behavior is required for completion.
The issue #3 acceptance record remains a factual record of checks already run.

## Backlog and release consequences

All 28 existing issue bodies and their local sources carry the website-first
scope. Issue #12 targets desktop website layouts and acceptance. Detail views,
settings, research, CI and deployment target website use. Issues #18 and #28
accept website releases without a mobile deliverable.

Issue numbers, milestones and dependency relationships stay the same. Completed
issues #1–#3 remain completed; their checklists and evidence are preserved.
No pending feature is marked shipped by this planning change. Later mobile work
requires an explicit scope decision and its own bounded issues.
