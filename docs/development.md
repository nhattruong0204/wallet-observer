# Development environment

This implements [WO-001 / issue #1](https://github.com/nhattruong0204/wallet-observer/issues/1). The repository has development tooling and a PostgreSQL database. The API, worker, frontend, migrations, and qualified provider integration follow in their own issues.

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

Python 3.12 and PostgreSQL 16 retain the plan's baseline. Node 24 replaces the suggested Node 22 baseline with the active LTS line. TypeScript 5.9 fits typescript-eslint's supported range. No application framework is installed by this issue.

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

The development Compose file binds the repository at `/workspaces/wallet-observer`. Database DNS is `db`, with no database port published on the host. The editor may forward only API port 8000 and frontend port 5173; neither has a server until WO-003. No production Compose configuration or deployment is provided here.

## Commands inside the container

| Command                  | Current behavior                                                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `make bootstrap`         | Check exact tool versions; `uv sync --locked`; `npm ci --ignore-scripts`; create mode-0600 `.env` placeholders only if missing |
| `make doctor`            | Check tool versions, non-root workspace write access, and an authenticated PostgreSQL `SELECT 1`                               |
| `make lint`              | Ruff checks/format checks, ESLint, and Prettier checks                                                                         |
| `make format`            | Apply Ruff and Prettier formatting to development files                                                                        |
| `make test`              | Run tests protecting local configuration and redacted diagnostics                                                              |
| `make provider-check`    | Report missing optional setting names; exit 2 when incomplete; make no live request                                            |
| `make db-shell`          | Connect with psql using container-local development credentials                                                                |
| `make dev`, `make build` | Exit 2 explaining the application is not implemented; foundation belongs to WO-003                                             |
| `make migrate`           | Exit 2; schema migrations belong to WO-004                                                                                     |
| `make fixtures`          | Verify sanitized real Solana captures and reviewed balance evidence offline                                                    |
| `make qualify-solana`    | Explicit bounded live Helius qualification probe; consumes provider credits; see the source contract                           |

The Python debugger runs the current file with the project's `.venv` interpreter. A browser debugger launch configuration is prepared for the future frontend and clearly marked as requiring WO-003. Python/TypeScript formatters, ESLint, debugger, and task settings are committed in `.vscode/`.

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

See [WO-001 acceptance record](acceptance/WO-001.md) for the tested platform, commands, results, and remaining limits. Windows/WSL instructions use the same Linux devcontainer, but should not be described as manually verified on Windows unless that verification actually occurs.
