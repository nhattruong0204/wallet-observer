.PHONY: help bootstrap doctor lint format test provider-check db-shell dev migrate build fixtures qualify-solana

help:
	@printf '%s\n' 'Run inside the devcontainer:' \
	  '  make bootstrap       Install locked tools and create .env if missing' \
	  '  make doctor          Verify pinned tools, workspace access, and database' \
	  '  make lint / format   Check / apply Python and JavaScript formatting' \
	  '  make test            Test development tooling' \
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
	uv run --locked ruff check scripts tests/tooling
	uv run --locked ruff format --check scripts tests/tooling
	npm run lint
	npm run format:check

format:
	uv run --locked ruff check --fix scripts tests/tooling
	uv run --locked ruff format scripts tests/tooling
	npm run format

test:
	uv run --locked pytest

db-shell:
	psql

fixtures:
	uv run --locked python scripts/solana_fixtures.py check

qualify-solana:
	uv run --locked --group qualification python scripts/qualify_solana.py --live

dev migrate build:
	@printf '%s\n' '$@ is not implemented yet. See docs/development.md and the issue dependencies.' >&2
	@exit 2
