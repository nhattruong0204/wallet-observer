# Development environment

The repository has a pinned devcontainer, FastAPI service, independent asynchronous worker, React frontend and PostgreSQL. Issue #3 adds the application foundation; migrations, collection and trade normalization remain later work. The default fixture mode needs no provider or Telegram credentials. See the [configuration contract](configuration.md).

## Pinned tools

| Tool                                  | Version | Source                                                                  |
| ------------------------------------- | ------- | ----------------------------------------------------------------------- |
| Python                                | 3.12.15 | Official Python container; supported security branch until October 2028 |
| Node.js                               | 24.21.0 | Official Node container; active LTS                                     |
| npm                                   | 11.21.0 | Exact npm registry release installed at image build                     |
| uv                                    | 0.12.22 | Official Astral container                                               |
| PostgreSQL server and psql/pg_isready | 16.15   | Same official PostgreSQL container                                      |
| Ruff                                  | 0.16.10 | `pyproject.toml` and `uv.lock`                                          |
| pytest                                | 9.1.1   | `pyproject.toml` and `uv.lock`                                          |
| debugpy                               | 1.8.22  | `pyproject.toml` and `uv.lock`                                          |
| ESLint                                | 10.12.0 | `package.json` and `package-lock.json`                                  |
| Prettier                              | 3.9.9   | `package.json` and `package-lock.json`                                  |
| TypeScript                            | 5.9.3   | `package.json` and `package-lock.json`                                  |
| typescript-eslint                     | 8.71.0  | `package.json` and `package-lock.json`                                  |

Python 3.12 and PostgreSQL 16 retain the plan's baseline. Node 24 replaces the suggested Node 22 baseline with the active LTS line. TypeScript 5.9 fits typescript-eslint's supported range. Application dependencies are pinned in `backend/pyproject.toml` and `frontend/package.json`; root `uv.lock` and `package-lock.json` lock both workspaces. The development tools remain pinned as above.

All four Docker source images are pinned by version and multi-platform SHA-256 digest in `.devcontainer/Dockerfile`; the database uses the same PostgreSQL digest. Debian system utilities (Git, Make, compiler, SSH client) use Bookworm's package repositories and receive security updates when the image is rebuilt. Their package revisions are not frozen. Python/JavaScript dependency resolutions and package integrity hashes are committed in the lockfiles. The doctor verifies the exact runtime versions against `scripts/toolchain.json`.

Primary references: [Python support/releases](https://www.python.org/downloads/), [Node 24 release](https://nodejs.org/en/blog/release/v24.21.0), [Node release schedule](https://github.com/nodejs/Release), [PostgreSQL support](https://www.postgresql.org/support/versioning/), [uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/), and [Dev Container Compose configuration](https://containers.dev/guide/dockerfile). Exact package versions and image digests were checked against their official registries on 3 October 2026.

## Windows with WSL2

1. Install Docker Desktop with WSL2 integration enabled for your Linux distribution. Install VS Code, its WSL extension, and its Dev Containers extension.
2. Keep the clone in the WSL Linux filesystem (for example, `~/wallet-observer`) for normal Linux permissions and file performance. From a WSL terminal:

   ```bash
   git clone https://github.com/nhattruong0204/wallet-observer.git
   cd wallet-observer
   code .
   ```

3. Select **Dev Containers: Reopen in Container**. The initial build downloads the pinned images. The development container starts after PostgreSQL becomes healthy and runs `make bootstrap` as the non-root `developer` user.
4. In the container terminal:

   ```bash
   make doctor
   make lint
   make test
   ```

No host Python, Node, uv, or provider credentials are required. An internet connection is required for the first image build and locked dependency install. Subsequent setup still uses the lockfiles.

## Linux

Install Docker Engine, the Compose plugin (v2 or newer), VS Code, and its Dev Containers extension. Verify that your user can run `docker version` and `docker compose version`. Clone/open the repository and use **Reopen in Container** as above. The Dev Containers extension adjusts the developer UID/GID to the Linux/WSL user so the bind-mounted repository remains writable.

For a terminal-only setup, set the build's UID/GID explicitly. Run these commands in the same host shell:

```bash
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
docker compose -f compose.dev.yml up -d --build --wait
docker compose -f compose.dev.yml exec dev make bootstrap
docker compose -f compose.dev.yml exec dev make doctor
docker compose -f compose.dev.yml exec dev make lint
docker compose -f compose.dev.yml exec dev make test
```

Use the editor devcontainer flow for its automatic UID handling. Terminal-only builds assume your numeric UID/GID are available in the base image; if a corporate host maps to an existing system account, use the editor flow or adapt the local override before building.

The development Compose file binds the repository at `/workspaces/wallet-observer`. Database DNS is `db`, with no database port published on the host. API port 8000 and frontend port 5173 are published on host loopback only. The editor also labels these ports. Worker health port 8001 is available only inside the container. Ports must be free before starting this development Compose project. No production Compose configuration or deployment is provided here.

## Commands inside the container

| Command                                    | Current behavior                                                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `make bootstrap`                           | Check exact tool versions; `uv sync --locked`; `npm ci --ignore-scripts`; create mode-0600 `.env` placeholders only if missing |
| `make doctor`                              | Check tool versions, non-root workspace write access, and an authenticated PostgreSQL `SELECT 1`                               |
| `make lint`                                | Ruff checks/format checks, ESLint, and Prettier checks                                                                         |
| `make format`                              | Apply Ruff and Prettier formatting to development files                                                                        |
| `make test`                                | Run offline Python service/tooling tests and frontend state tests                                                              |
| `make provider-check`                      | Report missing optional setting names; exit 2 when incomplete; make no live request                                            |
| `make db-shell`                            | Connect with psql using container-local development credentials                                                                |
| `make dev`                                 | Supervise API, worker and Vite; Ctrl-C stops their process groups                                                              |
| `make api`, `make worker`, `make frontend` | Run one service in its own terminal                                                                                            |
| `make config-check`                        | Validate startup settings with redacted errors; no network calls                                                               |
| `make build`                               | Type-check and build React assets; build the backend wheel/sdist                                                               |
| `make test-ui`                             | Run Chromium desktop/mobile checks against real local services; requires browser install below                                 |
| `make migrate`                             | Exit 2; schema migrations belong to WO-004                                                                                     |
| `make fixtures`                            | Verify sanitized real Solana captures and reviewed balance evidence offline                                                    |
| `make qualify-solana`                      | Explicit bounded live Helius qualification probe; consumes provider credits; see the source contract                           |

The Python debugger can launch the API or current file with the project's `.venv` interpreter. The browser debugger opens the running frontend at port 5173. Python/TypeScript formatters, ESLint, debugger, and task settings are committed in `.vscode/`.

## Run the application foundation

From the repository root inside the devcontainer:

```bash
make bootstrap
make doctor
make config-check
make dev
```

Open <http://localhost:5173>. The screen explicitly shows fixture mode, disabled
collection and an empty feed. `make dev` stops all three child process groups on
Ctrl-C or if any child exits. No Helius or Telegram call is made, even if existing
optional keys are present. PostgreSQL must be running. Use three terminals with
`make api`, `make worker`, and `make frontend` if you need separate logs.

While the services run, in another container terminal:

```bash
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://127.0.0.1:8001/health/ready
```

To test built assets without Vite, stop `make dev`, then run:

```bash
make build
make api
```

Open <http://localhost:8000>. Restart the API after the first build so it mounts
`frontend/dist`. The backend wheel does not bundle frontend assets; this is a
repository development command, not a production deployment package.

For browser tests, stop any separately running services first:

```bash
npx playwright install --with-deps chromium
make test-ui
```

Playwright starts and stops `make dev`, explicitly clears provider/Telegram
credentials and checks fixture, offline/retry, and mobile states against local
PostgreSQL. The first browser installation downloads Chromium and OS libraries;
ordinary `make test` does not require a browser or a running database. Screenshots
and browser results are ignored under `test-results/`.

## Directory map

| Path                                                       | Responsibility                                             |
| ---------------------------------------------------------- | ---------------------------------------------------------- |
| `backend/src/wallet_observer/settings.py`                  | Typed server-only configuration and safe errors            |
| `backend/src/wallet_observer/api.py`                       | API liveness/readiness/status and built frontend serving   |
| `backend/src/wallet_observer/worker.py`                    | Async worker lifecycle, dependency checks and local health |
| `backend/src/wallet_observer/database.py`                  | Bounded authenticated PostgreSQL readiness probe           |
| `backend/src/wallet_observer/logging.py`                   | Allowlisted JSON logs without raw URLs or exception text   |
| `frontend/src/`                                            | Minimal React workspace with empty/offline/retry states    |
| `scripts/run_dev.py`                                       | Local process supervision                                  |
| `backend/tests/`, `frontend/src/App.test.tsx`, `tests/ui/` | Service/privacy, UI state and browser verification         |
| `tests/fixtures/solana/`                                   | Reviewed source evidence; not runtime fake activity        |

## Local configuration

`.env.example` contains a development database URL and blank `HELIUS_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` placeholders. `make bootstrap` preserves an existing `.env`, including symlinks, and never prints its contents. `.env` and personal watchlists/data are ignored by Git; `.dockerignore` excludes the entire workspace from the image build apart from the tooling Dockerfile.

The development database credentials are public, intentionally local-only placeholders. They are supplied directly by `compose.dev.yml`, not loaded from your provider configuration. Production credentials and deployment are handled in WO-017. Avoid using the development Compose configuration for production.

`make provider-check` checks presence only, preferring environment variables to `.env`. It accepts simple `KEY=value` lines and quoted values; it does not execute shell code or interpolate variables. A successful presence check does not verify credentials, supported payloads, source access, or delivery. Bootstrap and doctor do not require any provider setting.

## Database persistence and shutdown

The `postgres-dev` named volume belongs to the Compose project. `docker compose -f compose.dev.yml stop` and `down` preserve it. Reopen the container or run `up -d --wait` to reuse the database. The database healthcheck uses `pg_isready`, and doctor separately verifies authenticated SQL access.

To verify persistence manually with disposable development data:

```bash
docker compose -f compose.dev.yml exec -T dev psql --set=ON_ERROR_STOP=1 \
  --command="CREATE TABLE IF NOT EXISTS wo001_persistence (id integer PRIMARY KEY); INSERT INTO wo001_persistence VALUES (1) ON CONFLICT DO NOTHING;"
docker compose -f compose.dev.yml restart db
docker compose -f compose.dev.yml up -d --wait
docker compose -f compose.dev.yml exec -T dev psql --set=ON_ERROR_STOP=1 \
  --command="SELECT id FROM wo001_persistence; DROP TABLE wo001_persistence;"
```

`docker compose -f compose.dev.yml down --volumes` deletes this project's development database. Use it only when deliberately discarding that data. Keep the same Compose project name when checking persistence across container recreation.

## Updating tool versions

Update the relevant Docker version/digest, `.python-version` or `.nvmrc`, package engines/manager, and `scripts/toolchain.json` together. Rebuild the devcontainer. Regenerate Python's lock with `uv lock` and JavaScript's with `npm install --package-lock-only --ignore-scripts`. Review the lockfile changes, then run bootstrap, doctor, lint, and tests. Normal setup must not regenerate either lockfile.

## Acceptance evidence

See [WO-001 acceptance record](acceptance/WO-001.md) for the environment and [WO-003 acceptance record](acceptance/WO-003.md) for application startup, browser behavior, database recovery and privacy checks. Windows/WSL instructions use the same Linux devcontainer, but should not be described as manually verified on Windows unless that verification actually occurs.
