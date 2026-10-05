"""Explicit test database only; each check owns a disposable, randomly named schema."""

import asyncio
import os
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from wallet_observer.db.migrations import migrate
from wallet_observer.settings import Settings


@pytest.fixture
def empty_database():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set TEST_DATABASE_URL to run isolated PostgreSQL integration checks")
    schema = "wo004_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    parts = urlsplit(dsn)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "options"]
    query.append(("options", f"-c search_path={schema},public"))
    scoped_dsn = urlunsplit(parts._replace(query=urlencode(query, quote_via=quote)))
    try:
        yield Settings(database_url=scoped_dsn, _env_file=None)
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def database(empty_database):
    asyncio.run(migrate(empty_database))
    return empty_database
