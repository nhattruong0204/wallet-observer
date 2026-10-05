"""Committed delivery positions, serialized independently from producer sequences."""

from psycopg.types.json import Jsonb

from wallet_observer.db.store import Store, transaction
from wallet_observer.settings import Settings


async def dispatch_batch(settings: Settings, *, limit: int = 100):
    """Only returns after commit. Never call from a producer's uncommitted transaction."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Dispatch batch must be between 1 and 1000")
    async with transaction(settings) as store:
        state = await store.one(
            "SELECT committed_position FROM delivery_state WHERE singleton FOR UPDATE"
        )
        position = state["committed_position"]
        rows = await (
            await store.connection.execute(
                """
            SELECT o.id, o.event_id, o.revision, r.payload FROM publication_outbox o
            JOIN event_revisions r ON r.event_id = o.event_id AND r.revision = o.revision
            WHERE o.dispatched_at IS NULL ORDER BY o.id LIMIT %s FOR UPDATE OF o
        """,
                (limit,),
            )
        ).fetchall()
        for row in rows:
            position += 1
            await store.connection.execute(
                """
                INSERT INTO delivery_log (position, event_id, revision, payload)
                VALUES (%s, %s, %s, %s)
            """,
                (position, row["event_id"], row["revision"], Jsonb(row["payload"])),
            )
            await store.connection.execute(
                "UPDATE publication_outbox SET dispatched_at = clock_timestamp() WHERE id = %s",
                (row["id"],),
            )
        await store.connection.execute(
            "UPDATE delivery_state SET committed_position = %s WHERE singleton", (position,)
        )
    return position


async def read_delivery(store: Store, *, after: int = 0, limit: int = 100):
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid delivery cursor or page size")
    # One statement snapshot binds the page and watermark, even during concurrent dispatch.
    rows = await (
        await store.connection.execute(
            """
        SELECT s.committed_position, d.position, d.event_id, d.revision, d.payload
        FROM delivery_state s LEFT JOIN LATERAL (
            SELECT position, event_id, revision, payload FROM delivery_log
            WHERE position > %s AND position <= s.committed_position
            ORDER BY position LIMIT %s
        ) d ON true WHERE s.singleton
    """,
            (after, limit),
        )
    ).fetchall()
    watermark = rows[0]["committed_position"]
    if after > watermark:
        raise ValueError("Delivery cursor is ahead of the committed watermark")
    events = [
        {k: v for k, v in row.items() if k != "committed_position"}
        for row in rows
        if row["position"] is not None
    ]
    return {
        "events": events,
        "next_cursor": events[-1]["position"] if events else after,
        "committed_position": watermark,
    }
