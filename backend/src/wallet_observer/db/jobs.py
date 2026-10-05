"""Durable work leases with fencing tokens, bounded attempts and redacted errors."""

import re
from datetime import timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from wallet_observer.db.store import Store


class LeaseLost(Exception):
    """The caller no longer owns an unexpired job lease."""


async def enqueue(
    store: Store, *, kind: str, object_key: str, payload: dict, max_attempts: int = 5
):
    row = await store.one(
        """
        INSERT INTO durable_jobs (kind, object_key, payload, max_attempts)
        VALUES (%s, %s, %s, %s) ON CONFLICT (kind, object_key)
        DO UPDATE SET object_key = EXCLUDED.object_key RETURNING id
    """,
        (kind, object_key, Jsonb(payload), max_attempts),
    )
    return row["id"]


async def claim(store: Store, *, kind: str, lease_seconds: float = 30):
    if not 0.1 <= lease_seconds <= 300:
        raise ValueError("Lease must be between 0.1 and 300 seconds")
    # A worker dying during its final attempt must not leave an immortal running job.
    await store.connection.execute(
        """
        UPDATE durable_jobs SET status = 'failed', lease_token = NULL, lease_until = NULL,
            last_error_code = 'lease_exhausted'
        WHERE id IN (
            SELECT id FROM durable_jobs WHERE kind = %s AND status = 'running'
                AND lease_until <= clock_timestamp() AND attempts >= max_attempts
            ORDER BY lease_until, id LIMIT 100 FOR UPDATE SKIP LOCKED
        )
    """,
        (kind,),
    )
    return await store.one(
        """
        WITH candidate AS (
            SELECT id FROM durable_jobs WHERE kind = %s AND attempts < max_attempts AND (
                (status = 'pending' AND available_at <= clock_timestamp()) OR
                (status = 'running' AND lease_until <= clock_timestamp())
            ) ORDER BY available_at, id LIMIT 1 FOR UPDATE SKIP LOCKED
        )
        UPDATE durable_jobs j SET status = 'running', attempts = attempts + 1,
            lease_token = %s, lease_until = clock_timestamp() + %s
        FROM candidate c WHERE j.id = c.id RETURNING j.*
    """,
        (kind, uuid4(), timedelta(seconds=lease_seconds)),
    )


async def finish(
    store: Store, *, job_id, lease_token, error_code: str | None = None, retry_seconds: float = 5
):
    if error_code is not None and not re.fullmatch(r"[a-z_]{1,64}", error_code):
        raise ValueError("Job errors must be static lowercase codes")
    if not 0 <= retry_seconds <= 3600:
        raise ValueError("Retry delay must be between 0 and 3600 seconds")
    row = await store.one(
        """
        UPDATE durable_jobs SET status = CASE
                WHEN %s::text IS NULL THEN 'completed'
                WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
            available_at = clock_timestamp() + %s, last_error_code = %s,
            lease_token = NULL, lease_until = NULL
        WHERE id = %s AND status = 'running' AND lease_token = %s
            AND lease_until > clock_timestamp()
        RETURNING status
    """,
        (error_code, timedelta(seconds=retry_seconds), error_code, job_id, lease_token),
    )
    if row is None:
        raise LeaseLost("Job lease expired or changed")
    return row["status"]
