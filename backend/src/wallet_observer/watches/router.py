"""Private single-operator watchlist API; no provider calls or product accounts."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from wallet_observer.db import transaction
from wallet_observer.logging import event
from wallet_observer.watches import store as watches
from wallet_observer.watches.models import GroupInput, ImportInput, WatchInput, WatchPatch


def watch_router(settings):
    async def database(request: Request):
        try:
            async with transaction(settings) as store:
                if request.method != "GET" and not request.url.path.endswith("/import/preview"):
                    # ponytail: serialize operator writes; revisit if contention is measured.
                    # Reads continue. Apply revalidates under the same lock as every other write.
                    await store.connection.execute(
                        "LOCK TABLE watches, watch_groups, watch_group_members "
                        "IN SHARE ROW EXCLUSIVE MODE"
                    )
                yield store
        except (psycopg.Error, OSError, TimeoutError):
            event("database_unavailable")
            raise HTTPException(503, "watchlist_storage_unavailable") from None

    Database = Annotated[object, Depends(database, scope="function")]
    router = APIRouter(prefix="/api")

    @router.get("/watches")
    async def listing(db: Database, include_removed: bool = False, group_id: UUID | None = None):
        return {
            "watches": await watches.list_watches(
                db, include_removed=include_removed, group_id=group_id
            )
        }

    @router.get("/watches/collection-intent")
    async def intent(db: Database):
        return {"collection": "disabled", "watches": await watches.collection_intent(db)}

    @router.get("/watches/export")
    async def export(db: Database, response: Response):
        response.headers["Content-Disposition"] = 'attachment; filename="watchlist.json"'
        fields = ("chain", "address", "alias", "note", "state", "groups")
        return {
            "version": 1,
            "rows": [{key: row[key] for key in fields} for row in await watches.list_watches(db)],
        }

    @router.post("/watches/import/preview")
    async def preview(batch: ImportInput, db: Database):
        return await watches.import_rows(db, batch)

    @router.post("/watches/import/apply")
    async def apply(batch: ImportInput, db: Database):
        return await watches.import_rows(db, batch, apply=True)

    @router.post("/watches")
    async def add(item: WatchInput, db: Database, response: Response):
        watch, created = await watches.add_watch(db, item)
        response.status_code = 201 if created else 200
        return {"created": created, "watch": watch}

    @router.get("/watches/{watch_id}")
    async def get(watch_id: UUID, db: Database):
        return {"watch": await watches.get_watch(db, watch_id)}

    @router.patch("/watches/{watch_id}")
    async def edit(watch_id: UUID, patch: WatchPatch, db: Database):
        return {"watch": await watches.patch_watch(db, watch_id, patch)}

    @router.delete("/watches/{watch_id}", status_code=204)
    async def remove(watch_id: UUID, db: Database):
        await watches.get_watch(db, watch_id)
        await db.connection.execute(
            "UPDATE watches SET state = 'removed' WHERE id = %s", (watch_id,)
        )

    @router.get("/groups")
    async def groups(db: Database):
        return {
            "groups": await (
                await db.connection.execute("SELECT id, name FROM watch_groups ORDER BY name")
            ).fetchall()
        }

    @router.post("/groups")
    async def add_group(item: GroupInput, db: Database, response: Response):
        row, created = await watches.group(db, item.name)
        response.status_code = 201 if created else 200
        return {"created": created, "group": row}

    @router.patch("/groups/{group_id}")
    async def rename_group(group_id: UUID, item: GroupInput, db: Database):
        if not await db.one("SELECT id FROM watch_groups WHERE id = %s", (group_id,)):
            raise HTTPException(404, "group_not_found")
        if await db.one(
            "SELECT id FROM watch_groups WHERE name = %s AND id <> %s", (item.name, group_id)
        ):
            raise HTTPException(409, "group_name_exists")
        return {
            "group": await db.one(
                "UPDATE watch_groups SET name = %s WHERE id = %s RETURNING id, name",
                (item.name, group_id),
            )
        }

    @router.delete("/groups/{group_id}", status_code=204)
    async def delete_group(group_id: UUID, db: Database):
        result = await db.connection.execute("DELETE FROM watch_groups WHERE id = %s", (group_id,))
        if not result.rowcount:
            raise HTTPException(404, "group_not_found")

    return router
