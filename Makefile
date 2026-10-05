.PHONY: help bootstrap doctor lint format test test-integration test-ui config-check api worker frontend provider-check db-shell dev migrate build fixtures qualify-solana

help:
	@printf '%s\n' 'Run inside the devcontainer:' \
	  '  make bootstrap       Install locked tools and create .env if missing' \
	  '  make dev             Start API, worker and frontend; Ctrl-C stops all' \
	  '  make api / worker / frontend  Start one service' \
	  '  make config-check    Validate settings without contacting providers' \
	  '  make build           Build backend package and frontend assets' \
	  '  make doctor          Verify pinned tools, workspace access, and database' \
	  '  make lint / format   Check / apply Python and JavaScript formatting' \
	  '  make test            Run offline backend, tooling and frontend tests' \
	  '  make migrate         Apply checksummed PostgreSQL migrations' \
	  '  make test-integration  Check persistence using explicit TEST_DATABASE_URL' \
	  '  make fixtures        Verify sanitized source evidence offline' \
	  '  make qualify-solana  Opt-in bounded live Helius probe (consumes credits)' \
	  '  make provider-check  Report missing configuration without network calls' \
	  '  make db-shell        Open the development database'

bootstrap:
	python scripts/dev.py bootstrap

doctor:
	python scripts/dev.py doctor

provider-check:
	python scripts/dev.py provider-check

lint:
	uv run --locked ruff check scripts tests/tooling tests/integration backend
	uv run --locked ruff format --check scripts tests/tooling tests/integration backend
	npm run lint
	npm run format:check

format:
	uv run --locked ruff check --fix scripts tests/tooling tests/integration backend
	uv run --locked ruff format scripts tests/tooling tests/integration backend
	npm run format

test:
	uv run --locked pytest
	npm test

test-ui:
	npm run test:ui

test-integration:
	@test -n "$${TEST_DATABASE_URL:-}" || { printf '%s\n' 'Set TEST_DATABASE_URL to a disposable PostgreSQL database.' >&2; exit 2; }
	uv run --locked pytest tests/integration

config-check:
	uv run --locked wallet-observer config-check

dev:
	uv run --locked python scripts/run_dev.py

api:
	uv run --locked wallet-observer api --host 0.0.0.0

worker:
	uv run --locked wallet-observer worker

frontend:
	npm run dev --workspace frontend

build:
	npm run build --workspace frontend
	uv build --package wallet-observer

db-shell:
	psql

fixtures:
	uv run --locked python scripts/solana_fixtures.py check

qualify-solana:
	uv run --locked --group qualification python scripts/qualify_solana.py --live

migrate:
	uv run --locked wallet-observer migrate
