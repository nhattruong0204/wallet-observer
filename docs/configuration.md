# Application configuration and service contract

Implemented for [issue #3 / WO-003](https://github.com/nhattruong0204/wallet-observer/issues/3).
Run commands from the repository root inside the devcontainer. API and worker
use the same typed settings model. Process environment overrides the local `.env`;
defaults apply only to optional settings. Existing `.env` files are preserved by bootstrap.

| Variable                   | Required/default  | Meaning                                                                                                                                                                           |
| -------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`             | Required          | PostgreSQL URL with host, user and database. Both `postgresql://` and existing `postgresql+psycopg://` forms are accepted. Keep passwords private; URL-encode special characters. |
| `APP_MODE`                 | `fixture`         | `fixture` or `live`. Fixture mode requires all integrations disabled and makes no external provider/Telegram requests.                                                            |
| `DATABASE_TIMEOUT_SECONDS` | `3`, range 0.1–10 | Overall asynchronous connection/query readiness timeout.                                                                                                                          |
| `WORKER_POLL_SECONDS`      | `5`, range 0.1–60 | Worker dependency-check interval.                                                                                                                                                 |
| `HELIUS_ENABLED`           | `false`           | Reserved feature switch. Enabling requires a key, but startup still refuses until collector issue #6 is implemented.                                                              |
| `TELEGRAM_ENABLED`         | `false`           | Reserved feature switch. Enabling requires bot/chat settings, but startup still refuses until issue #14 is implemented.                                                           |
| `HELIUS_API_KEY`           | Empty/optional    | Server-side secret; unused by this foundation.                                                                                                                                    |
| `TELEGRAM_BOT_TOKEN`       | Empty/optional    | Server-side secret; unused by this foundation.                                                                                                                                    |
| `TELEGRAM_CHAT_ID`         | Empty/optional    | Private destination; unused by this foundation.                                                                                                                                   |

`make config-check` validates without connecting to a database or provider.
An invalid setting exits 2 with its field name and a corrective message; input
values and exception context are excluded. Unknown `.env` fields are ignored so
future tooling settings can coexist. Boolean flags accept Pydantic's normal
boolean spellings; prefer explicit `true`/`false` in `.env`.

`live` currently means an empty foundation with disabled integrations, not a
working collector. Setting a key alone never turns on collection. No mode sends
transactions or requires a wallet signing key. Raw source captures and personal
watchlists remain outside the application status response and browser bundle.

## Services and health

One API, one independent worker process, and PostgreSQL remain the architecture.
Vite is an additional development server; the API can serve its built static
assets after `make build`. Worker HTTP endpoints are only a local health surface,
not a separate business API. PostgreSQL schema and transaction primitives are provided by issue #4; see the [persistence contract](data-model.md). No Redis or broker is required.

| Endpoint            | API (`8000`)                                                          | Worker (`8001`, container loopback only)                                  |
| ------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `GET /health/live`  | 200 while the process handles requests                                | 200 while the process handles requests                                    |
| `GET /health/ready` | Authenticated `SELECT 1`; 200 or 503                                  | Latest bounded database check plus fresh, running worker loop; 200 or 503 |
| `GET /api/status`   | Allowlisted mode, database availability and disabled capability flags | Not available                                                             |

Database loss leaves liveness healthy and readiness at 503. The API probes on each
readiness/status request. Worker readiness reflects its last check, so detection
can lag by the poll interval plus database timeout (defaults: at most roughly
eight seconds). An unexpected worker-loop failure or stale heartbeat cannot
report ready. Worker startup remains unready until its first successful check.
Database recovery restores readiness without a process restart.

The API does not claim the worker is healthy; its readiness covers its own database
dependency. This worker runs a lifecycle/dependency loop only. Durable jobs,
ingestion and worker scheduling belong to subsequent issues. Checkpoint primitives and deliberate migrations are available through the persistence layer. SIGTERM/SIGINT
stop the server and let the worker finish its bounded check and exit.

The status response contains only:

```json
{
  "mode": "fixture",
  "database": "ready",
  "collection": "disabled",
  "notifications": "disabled"
}
```

This is an application status example, not a provider fixture. Readiness does not
assert that wallet collection is enabled, history is complete, or the beta is released.

## Logs and frontend boundary

API and worker write JSON lines with UTC timestamp, level, service and an
allowlisted event name. Configuration errors contain static validation messages.
Database transition logs contain no DSN. Arbitrary library messages, arguments,
request URLs and exception tracebacks are deliberately excluded; Uvicorn access
logging is disabled. Unexpected failures log a stable event and affect readiness
or return a generic 500. Richer safe diagnostics belong to the observability work.

The frontend uses relative `/api/status` requests; Vite proxies these to the local
API. It polls five seconds after a request completes, aborts requests after four
seconds and offers retry. API loss and database loss both produce an explicit
offline state, while successful fixture startup shows an honest empty state.
No fake wallet balances, executions or watchlist counts are shown.

Vite's environment prefix list is empty: server environment values are not
automatically exposed. The frontend root is `frontend/`, and the repository `.env`
is not loaded by it. `make dev` also removes known server secrets from the frontend
child's inherited environment. Vite serves only the frontend and dependency
directories, with explicit denials for environment files, watchlists and private
capture directories. Built assets must still be scanned when adding
future configuration; never import backend configuration into frontend source.

Primary implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[Pydantic settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
[Psycopg async connections](https://www.psycopg.org/psycopg3/docs/advanced/async.html),
[Vite environment exposure](https://vite.dev/config/shared-options#envprefix),
[uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).
