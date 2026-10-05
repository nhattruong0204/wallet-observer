"""Numbered, checksummed PostgreSQL migrations, applied atomically under a lock."""

import hashlib
import re
from pathlib import Path

import psycopg

from wallet_observer.settings import Settings

MIGRATION_LOCK = 879_004_001


class MigrationError(Exception):
    """Static diagnostics only: never include a DSN or database exception."""


def migration_files(directory: Path | None = None):
    if directory is None:
        bundled = Path(__file__).with_name("migrations")
        directory = bundled if bundled.is_dir() else Path(__file__).parents[3] / "migrations"
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        if not re.fullmatch(r"\d{4}_[a-z_]+\.sql", path.name):
            raise MigrationError("Invalid migration filename")
        contents = path.read_bytes()
        migrations.append(
            (
                int(path.name[:4]),
                path.name,
                hashlib.sha256(contents).hexdigest(),
                contents.decode("utf-8"),
            )
        )
    if not migrations or [m[0] for m in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError("Migration versions must be contiguous starting at 0001")
    return migrations


async def migrate(settings: Settings, *, target: int | None = None, directory: Path | None = None):
    migrations = migration_files(directory)
    target = len(migrations) if target is None else target
    if type(target) is not int or not 1 <= target <= len(migrations):
        raise MigrationError("Unknown migration target")
    async with await psycopg.AsyncConnection.connect(
        settings.database_dsn(), connect_timeout=max(1, int(settings.database_timeout_seconds))
    ) as connection:
        await connection.execute("SET LOCAL lock_timeout = '10s'")
        await connection.execute("SET LOCAL statement_timeout = '30s'")
        await connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version integer PRIMARY KEY, name text NOT NULL, sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
            )
        """)
        rows = await (
            await connection.execute(
                "SELECT version, name, sha256 FROM schema_migrations ORDER BY version"
            )
        ).fetchall()
        if rows != [m[:3] for m in migrations[: len(rows)]]:
            raise MigrationError(
                "Applied migrations differ from this release; restore matching files"
            )
        if rows and rows[-1][0] > target:
            raise MigrationError("Downgrades are unsupported; restore a tested backup")
        applied = []
        for version, name, checksum, contents in migrations[len(rows) : target]:
            await connection.execute(contents, prepare=False)
            await connection.execute(
                "INSERT INTO schema_migrations (version, name, sha256) VALUES (%s, %s, %s)",
                (version, name, checksum),
            )
            applied.append(version)
        return applied
