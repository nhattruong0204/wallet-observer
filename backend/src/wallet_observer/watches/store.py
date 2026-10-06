"""Watch operations share the existing transaction and never delete wallet history."""

from fastapi import HTTPException
from pydantic import ValidationError

from wallet_observer.watches.models import WatchInput, validation_details

WATCH_SELECT = """
    SELECT w.id, w.wallet_id, wa.chain, wa.address, w.alias, w.note, w.state, w.created_at,
           'manual' AS label_source,
           COALESCE((SELECT jsonb_agg(g.name ORDER BY g.name)
                     FROM watch_group_members m JOIN watch_groups g ON g.id = m.group_id
                     WHERE m.watch_id = w.id), '[]'::jsonb) AS groups
    FROM watches w JOIN wallets wa ON wa.id = w.wallet_id
"""


async def list_watches(store, *, include_removed=False, group_id=None):
    return await (
        await store.connection.execute(
            WATCH_SELECT
            + """
        WHERE (%s OR w.state <> 'removed') AND (%s::uuid IS NULL OR EXISTS (
            SELECT 1 FROM watch_group_members m WHERE m.watch_id = w.id AND m.group_id = %s
        )) ORDER BY wa.chain, wa.address
        """,
            (include_removed, group_id, group_id),
        )
    ).fetchall()


async def get_watch(store, watch_id):
    row = await store.one(WATCH_SELECT + " WHERE w.id = %s", (watch_id,))
    if row is None:
        raise HTTPException(404, "watch_not_found")
    return row


async def group(store, name):
    row = await store.one("SELECT id, name FROM watch_groups WHERE name = %s", (name,))
    if row:
        return row, False
    return await store.one(
        "INSERT INTO watch_groups (name) VALUES (%s) RETURNING id, name", (name,)
    ), True


async def set_groups(store, watch_id, names):
    await store.connection.execute(
        "DELETE FROM watch_group_members WHERE watch_id = %s", (watch_id,)
    )
    for name in sorted(set(names)):
        row, _ = await group(store, name)
        await store.connection.execute(
            "INSERT INTO watch_group_members (watch_id, group_id) VALUES (%s, %s)",
            (watch_id, row["id"]),
        )


async def add_watch(store, item):
    wallet_id = await store.wallet(item.chain, item.address)
    existing = await store.one("SELECT id FROM watches WHERE wallet_id = %s", (wallet_id,))
    if existing:
        return await get_watch(store, existing["id"]), False
    row = await store.one(
        """INSERT INTO watches (wallet_id, alias, note, state) VALUES (%s, %s, %s, %s)
           RETURNING id""",
        (wallet_id, item.alias, item.note, item.state),
    )
    await set_groups(store, row["id"], item.groups)
    return await get_watch(store, row["id"]), True


async def patch_watch(store, watch_id, patch):
    current = await get_watch(store, watch_id)
    # Existing storage APIs allow sanitized fixture aliases. Do not activate one as an address.
    changes = patch.model_dump(exclude_unset=True)
    if changes.get("state") == "active":
        try:
            WatchInput(chain=current["chain"], address=current["address"])
        except ValidationError:
            raise HTTPException(422, "unsupported_or_invalid_address") from None
    current.update(changes)
    await store.connection.execute(
        "UPDATE watches SET alias = %s, note = %s, state = %s WHERE id = %s",
        (current["alias"], current["note"], current["state"], watch_id),
    )
    if "groups" in changes:
        await set_groups(store, watch_id, changes["groups"])
    return await get_watch(store, watch_id)


async def collection_intent(store):
    # Unique watches.wallet_id means one target per wallet even across multiple groups.
    return await (
        await store.connection.execute("""
        SELECT w.id AS watch_id, w.wallet_id, wa.chain, wa.address
        FROM watches w JOIN wallets wa ON wa.id = w.wallet_id
        WHERE w.state = 'active' AND wa.chain = 'solana' ORDER BY wa.address
    """)
    ).fetchall()


async def import_rows(store, batch, *, apply=False):
    existing = {
        (r["chain"], r["address"]): r for r in await list_watches(store, include_removed=True)
    }
    seen, parsed, rows = set(), [], []
    for index, raw in enumerate(batch.rows, 1):
        try:
            item = WatchInput.model_validate(raw)
        except ValidationError as error:
            rows.append({"row": index, "status": "invalid", "errors": validation_details(error)})
            continue
        key = item.chain, item.address
        if key in existing:
            rows.append(
                {
                    "row": index,
                    "status": "duplicate",
                    "reason": "existing",
                    "watch_id": str(existing[key]["id"]),
                    "state": existing[key]["state"],
                }
            )
        elif key in seen:
            rows.append({"row": index, "status": "duplicate", "reason": "earlier_row"})
        else:
            seen.add(key)
            rows.append({"row": index, "status": "valid"})
            parsed.append((rows[-1], item))
    counts = {
        kind: sum(r["status"] == kind for r in rows) for kind in ("valid", "duplicate", "invalid")
    }
    result = {"applied": False, "counts": counts, "rows": rows}
    if apply:
        if counts["invalid"]:
            raise HTTPException(422, {"code": "invalid_import", **result})
        for report, item in parsed:
            watch, _ = await add_watch(store, item)
            report["watch_id"] = watch["id"]
        result["applied"] = True
    return result
