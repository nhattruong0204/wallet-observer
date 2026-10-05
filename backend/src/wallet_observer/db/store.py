"""Compose writes in one transaction; no method commits independently."""

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from wallet_observer.db.models import CanonicalEvent
from wallet_observer.settings import Settings


class RevisionConflict(Exception):
    """A concurrent or stale canonical revision needs to be re-read."""


class CheckpointConflict(Exception):
    """The expected checkpoint changed or its proposed boundary would regress."""


def digest(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


@asynccontextmanager
async def transaction(settings: Settings):
    async with await psycopg.AsyncConnection.connect(
        settings.database_dsn(),
        row_factory=dict_row,
        connect_timeout=max(1, int(settings.database_timeout_seconds)),
    ) as connection:
        await connection.execute("SET LOCAL TIME ZONE 'UTC'")
        await connection.execute("SET LOCAL lock_timeout = '5s'")
        await connection.execute("SET LOCAL statement_timeout = '15s'")
        yield Store(connection)


class Store:
    def __init__(self, connection):
        if connection.autocommit:
            raise ValueError("Persistence requires an explicit transaction")
        self.connection = connection

    async def one(self, query, params=()):
        return await (await self.connection.execute(query, params)).fetchone()

    async def wallet(self, chain: str, address: str) -> UUID:
        row = await self.one(
            """
            INSERT INTO wallets (chain, address) VALUES (%s, %s)
            ON CONFLICT (chain, address) DO NOTHING RETURNING id
        """,
            (chain, address),
        )
        if row is None:
            row = await self.one(
                "SELECT id FROM wallets WHERE chain = %s AND address = %s", (chain, address)
            )
        return row["id"]

    async def token(self, chain: str, address: str) -> UUID:
        row = await self.one(
            """
            INSERT INTO tokens (chain, address) VALUES (%s, %s)
            ON CONFLICT (chain, address) DO NOTHING RETURNING id
        """,
            (chain, address),
        )
        if row is None:
            row = await self.one(
                "SELECT id FROM tokens WHERE chain = %s AND address = %s", (chain, address)
            )
        return row["id"]

    async def source_record(
        self,
        *,
        provider: str,
        chain: str,
        source_event_id: str,
        payload: dict,
        replay: bool = False,
        retention_days: int = 7,
    ):
        if type(retention_days) is not int or not 1 <= retention_days <= 90:
            raise ValueError("Payload retention must be between 1 and 90 days")
        row = await self.one(
            """
            INSERT INTO raw_source_events (provider, chain, source_event_id)
            VALUES (%s, %s, %s) ON CONFLICT (provider, chain, source_event_id)
            DO UPDATE SET source_event_id = EXCLUDED.source_event_id RETURNING id
        """,
            (provider, chain, source_event_id),
        )
        await self.connection.execute(
            """
            INSERT INTO source_payloads
                (source_record_id, payload_sha256, payload, replay, expires_at)
            VALUES (%s, %s, %s, %s, clock_timestamp() + %s)
            ON CONFLICT (source_record_id, payload_sha256) DO NOTHING
        """,
            (row["id"], digest(payload), Jsonb(payload), replay, timedelta(days=retention_days)),
        )
        return row["id"]

    async def write_event(
        self, source_record_id: UUID, event: CanonicalEvent, *, expected_revision: int
    ):
        """CAS revisions; an exact replay is a no-op even with a stale expected revision."""
        # Revalidate even model_copy()/model_construct() instances before any SQL write.
        event = CanonicalEvent.model_validate(event)
        wallet_id = await self.wallet(event.chain, event.wallet_address)
        identity = (
            event.chain,
            event.transaction_id,
            event.instruction_index,
            event.inner_instruction_index,
            wallet_id,
        )
        await self.connection.execute(
            """
            INSERT INTO canonical_events
                (chain, transaction_id, instruction_index, inner_instruction_index, wallet_id,
                 occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """,
            (*identity, event.occurred_at),
        )
        current = await self.one(
            """
            SELECT id, current_revision FROM canonical_events
            WHERE chain = %s AND transaction_id = %s AND instruction_index = %s
                AND inner_instruction_index IS NOT DISTINCT FROM %s AND wallet_id = %s
            FOR UPDATE
        """,
            identity,
        )
        event_id, revision = current["id"], current["current_revision"]
        await self.connection.execute(
            """
            INSERT INTO event_sources (event_id, source_record_id, chain)
            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
        """,
            (event_id, source_record_id, event.chain),
        )
        # Replay transport is provenance, not a new economic revision.
        content = event.model_dump(mode="json", exclude={"replay"})
        checksum = digest(content)
        previous = await self.one(
            """
            SELECT content_sha256 FROM event_revisions WHERE event_id = %s AND revision = %s
        """,
            (event_id, revision),
        )
        if previous and previous["content_sha256"] == checksum:
            return event_id, revision
        if revision != expected_revision:
            raise RevisionConflict("Canonical revision changed; re-read before applying correction")
        revision += 1
        snapshot = {
            **content,
            "event_id": str(event_id),
            "revision": revision,
            "replay": event.replay,
        }
        await self.connection.execute(
            """
            INSERT INTO event_revisions (event_id, revision, kind, chain_confirmation,
                source_order_status, coverage_status, content_sha256, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                event_id,
                revision,
                event.kind,
                event.chain_confirmation,
                event.source_order_status,
                event.coverage_status,
                checksum,
                Jsonb(snapshot),
            ),
        )
        await self.connection.execute(
            "UPDATE canonical_events SET occurred_at = %s WHERE id = %s",
            (event.occurred_at, event_id),
        )
        if event.execution_status is not None:
            execution = await self.one(
                """
                INSERT INTO executions (event_id, chain, status, execution_usd, valuation_status)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (event_id) DO UPDATE SET
                    status = EXCLUDED.status, execution_usd = EXCLUDED.execution_usd,
                    valuation_status = EXCLUDED.valuation_status RETURNING id
            """,
                (
                    event_id,
                    event.chain,
                    event.execution_status,
                    event.execution_usd,
                    "known" if event.execution_usd is not None else "unavailable",
                ),
            )
            await self.connection.execute(
                "DELETE FROM execution_legs WHERE execution_id = %s", (execution["id"],)
            )
            for index, leg in enumerate(event.legs):
                token_id = await self.token(event.chain, leg.token_address)
                await self.connection.execute(
                    """
                    INSERT INTO execution_legs (execution_id, chain, leg_index, token_id,
                        direction, raw_quantity, token_decimals)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        execution["id"],
                        event.chain,
                        index,
                        token_id,
                        leg.direction,
                        leg.raw_quantity,
                        leg.token_decimals,
                    ),
                )
        else:
            # A reclassification must never leave an old successful execution eligible.
            await self.connection.execute(
                "UPDATE executions SET status = 'reverted' WHERE event_id = %s", (event_id,)
            )
        return event_id, revision

    async def advance_checkpoint(
        self,
        *,
        provider: str,
        chain: str,
        scope: str,
        safe_slot: int,
        expected_version: int,
        cursor=None,
    ):
        await self.connection.execute(
            """
            INSERT INTO source_checkpoints (provider, chain, scope) VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """,
            (provider, chain, scope),
        )
        row = await self.one(
            """
            UPDATE source_checkpoints SET safe_slot = %s, cursor = %s,
                version = version + 1, updated_at = clock_timestamp()
            WHERE provider = %s AND chain = %s AND scope = %s AND version = %s
                AND (safe_slot IS NULL OR safe_slot <= %s)
            RETURNING version
        """,
            (
                safe_slot,
                Jsonb(cursor) if cursor is not None else None,
                provider,
                chain,
                scope,
                expected_version,
                safe_slot,
            ),
        )
        if row is None:
            raise CheckpointConflict("Checkpoint changed or proposed boundary regressed")
        return row["version"]

    async def expire_payloads(self, *, limit: int = 100):
        if not 1 <= limit <= 1000:
            raise ValueError("Retention batch must be between 1 and 1000")
        result = await self.connection.execute(
            """
            DELETE FROM source_payloads WHERE id IN (
                SELECT id FROM source_payloads WHERE expires_at <= clock_timestamp()
                ORDER BY expires_at, id LIMIT %s FOR UPDATE SKIP LOCKED
            )
        """,
            (limit,),
        )
        return result.rowcount
