"""Bounded authenticated readiness check; schema and persistence belong to WO-004."""

import asyncio

import psycopg

from wallet_observer.settings import Settings


async def check_database(settings: Settings) -> bool:
    try:
        async with asyncio.timeout(settings.database_timeout_seconds):
            async with await psycopg.AsyncConnection.connect(
                settings.database_dsn(),
                autocommit=True,
                connect_timeout=max(1, int(settings.database_timeout_seconds)),
            ) as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    return await cursor.fetchone() == (1,)
    except (psycopg.Error, OSError, TimeoutError):
        # Database exception messages can include the full DSN, role or host.
        return False
