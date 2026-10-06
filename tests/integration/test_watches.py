"""Exercise private watchlist HTTP operations against isolated real PostgreSQL schemas."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from wallet_observer.api import create_app
from wallet_observer.db import transaction
from wallet_observer.watches import store as watches

# Public account syntax vectors, not a personal watchlist or fabricated provider events.
ADDRESS = "So11111111111111111111111111111111111111112"
SECOND = "11111111111111111111111111111111"


@pytest.fixture
def client(database):
    with TestClient(create_app(database)) as client:
        yield client


def add(client, **fields):
    response = client.post("/api/watches", json={"address": ADDRESS, **fields})
    assert response.status_code == 201, response.text
    return response.json()["watch"]


def test_crud_manual_labels_groups_and_idempotent_creation(client):
    watch = add(client, alias="A manual label", note="private note", groups=[" Alpha ", "Alpha"])
    assert watch["address"] == ADDRESS and watch["label_source"] == "manual"
    assert watch["groups"] == ["Alpha"]
    duplicate = client.post("/api/watches", json={"address": ADDRESS, "alias": "overwritten?"})
    assert duplicate.status_code == 200
    assert duplicate.json() == {"created": False, "watch": watch}
    patch = client.patch(
        f"/api/watches/{watch['id']}", json={"alias": None, "note": "edited", "groups": []}
    )
    assert patch.status_code == 200
    current = patch.json()["watch"]
    assert current["alias"] is None and current["note"] == "edited" and current["groups"] == []
    assert client.get(f"/api/watches/{watch['id']}").json()["watch"] == current
    assert len(client.get("/api/watches").json()["watches"]) == 1
    assert client.get("/api/watches").headers["cache-control"] == "no-store"
    assert client.get("/api/status").json()["collection"] == "disabled"


def test_pause_remove_restore_preserve_history_and_collection_intent(client, database):
    watch = add(client, groups=["one", "two"])

    async def history():
        async with transaction(database) as store:
            await store.connection.execute(
                """INSERT INTO canonical_events
                   (chain, transaction_id, instruction_index, wallet_id)
                   VALUES ('solana', 'controlled-history-marker', 0, %s)""",
                (watch["wallet_id"],),
            )

    asyncio.run(history())
    assert len(client.get("/api/watches/collection-intent").json()["watches"]) == 1
    for state in ("paused", "resolving", "unsupported", "error"):
        assert client.patch(f"/api/watches/{watch['id']}", json={"state": state}).status_code == 200
        assert client.get("/api/watches/collection-intent").json()["watches"] == []
    assert client.patch(f"/api/watches/{watch['id']}", json={"state": "active"}).status_code == 200
    for _ in range(2):
        assert client.delete(f"/api/watches/{watch['id']}").status_code == 204
    assert client.get("/api/watches").json()["watches"] == []
    assert client.get("/api/watches/collection-intent").json()["watches"] == []
    assert (
        client.get("/api/watches?include_removed=true").json()["watches"][0]["state"] == "removed"
    )
    duplicate = client.post("/api/watches", json={"address": ADDRESS}).json()
    assert not duplicate["created"] and duplicate["watch"]["state"] == "removed"
    assert client.patch(f"/api/watches/{watch['id']}", json={"state": "active"}).status_code == 200
    assert len(client.get("/api/watches/collection-intent").json()["watches"]) == 1

    async def preserved():
        async with transaction(database) as store:
            assert (await store.one("SELECT count(*) AS n FROM canonical_events"))["n"] == 1
            assert (await store.one("SELECT count(*) AS n FROM watches"))["n"] == 1
            assert (await store.one("SELECT count(*) AS n FROM identity_wallet_links"))["n"] == 0

    asyncio.run(preserved())


def test_group_rename_conflict_filter_and_delete_preserve_watches(client):
    watch = add(client, groups=["alpha", "beta"])
    groups = {g["name"]: g["id"] for g in client.get("/api/groups").json()["groups"]}
    assert client.post("/api/groups", json={"name": "alpha"}).status_code == 200
    assert client.post("/api/groups", json={"name": "empty"}).status_code == 201
    alpha = groups["alpha"]
    assert client.patch(f"/api/groups/{alpha}", json={"name": "beta"}).status_code == 409
    assert client.patch(f"/api/groups/{alpha}", json={"name": "renamed"}).status_code == 200
    assert len(client.get(f"/api/watches?group_id={alpha}").json()["watches"]) == 1
    assert client.get(f"/api/watches/{watch['id']}").json()["watch"]["groups"] == [
        "beta",
        "renamed",
    ]
    assert client.delete(f"/api/groups/{alpha}").status_code == 204
    assert client.get(f"/api/watches/{watch['id']}").json()["watch"]["groups"] == ["beta"]
    assert client.get(f"/api/watches?group_id={alpha}").json()["watches"] == []
    assert len(client.get("/api/watches/collection-intent").json()["watches"]) == 1
    assert client.delete(f"/api/groups/{alpha}").status_code == 404


def test_preview_mixed_rows_and_atomic_rejection_do_not_write(client):
    add(client)
    batch = {
        "version": 1,
        "rows": [
            {"address": SECOND, "groups": ["should-not-exist"]},
            {"address": SECOND},
            {"address": ADDRESS},
            {"address": "PRIVATE_INVALID_ADDRESS"},
            {"address": SECOND, "PRIVATE_FIELD": "PRIVATE_VALUE"},
            "PRIVATE_RAW_ROW",
        ],
    }
    preview = client.post("/api/watches/import/preview", json=batch)
    assert preview.status_code == 200
    assert preview.json()["counts"] == {"valid": 1, "duplicate": 2, "invalid": 3}
    assert [r["status"] for r in preview.json()["rows"]] == [
        "valid",
        "duplicate",
        "duplicate",
        "invalid",
        "invalid",
        "invalid",
    ]
    assert not preview.json()["applied"]
    failed = client.post("/api/watches/import/apply", json=batch)
    assert failed.status_code == 422 and not failed.json()["detail"]["applied"]
    for marker in ("PRIVATE_INVALID_ADDRESS", "PRIVATE_FIELD", "PRIVATE_VALUE", "PRIVATE_RAW_ROW"):
        assert marker not in failed.text
    assert len(client.get("/api/watches").json()["watches"]) == 1
    assert client.get("/api/groups").json()["groups"] == []


def test_import_revalidates_stale_preview_and_never_reactivates_removed(client):
    batch = {"version": 1, "rows": [{"address": ADDRESS, "alias": "import label"}]}
    assert client.post("/api/watches/import/preview", json=batch).json()["counts"]["valid"] == 1
    watch = add(client, alias="saved label")
    client.delete(f"/api/watches/{watch['id']}")
    applied = client.post("/api/watches/import/apply", json=batch)
    assert applied.status_code == 200
    assert applied.json()["counts"] == {"valid": 0, "duplicate": 1, "invalid": 0}
    row = client.get(f"/api/watches/{watch['id']}").json()["watch"]
    assert row["state"] == "removed" and row["alias"] == "saved label"


def test_import_export_roundtrip_and_explicit_duplicate_reporting(client):
    batch = {
        "version": 1,
        "rows": [
            {
                "chain": "solana",
                "address": ADDRESS,
                "alias": "label",
                "note": None,
                "groups": ["g"],
                "state": "paused",
            },
            {
                "chain": "solana",
                "address": SECOND,
                "alias": None,
                "note": "note",
                "groups": [],
                "state": "active",
            },
        ],
    }
    applied = client.post("/api/watches/import/apply", json=batch)
    assert applied.status_code == 200 and applied.json()["applied"]
    assert applied.json()["counts"] == {"valid": 2, "duplicate": 0, "invalid": 0}
    exported = client.get("/api/watches/export")
    assert exported.headers["cache-control"] == "no-store"
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.json() == {
        "version": 1,
        "rows": sorted(batch["rows"], key=lambda r: r["address"]),
    }
    repeated = client.post("/api/watches/import/apply", json=exported.json()).json()
    assert repeated["counts"] == {"valid": 0, "duplicate": 2, "invalid": 0}


def test_storage_failure_rolls_back_entire_import(client, monkeypatch, caplog):
    original = watches.add_watch
    calls = 0

    async def fail_second(store, item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise psycopg.OperationalError("PRIVATE_DATABASE_SECRET")
        return await original(store, item)

    monkeypatch.setattr(watches, "add_watch", fail_second)
    response = client.post(
        "/api/watches/import/apply",
        json={
            "version": 1,
            "rows": [
                {"address": ADDRESS, "groups": ["rolled-back"]},
                {"address": SECOND},
            ],
        },
    )
    assert response.status_code == 503 and "PRIVATE_DATABASE_SECRET" not in response.text
    assert "PRIVATE_DATABASE_SECRET" not in caplog.text
    assert client.get("/api/watches").json()["watches"] == []
    assert client.get("/api/groups").json()["groups"] == []


def test_concurrent_single_and_bulk_additions_have_one_intent(client):
    def create(i):
        if i % 2:
            return client.post("/api/watches", json={"address": ADDRESS, "groups": ["g"]})
        return client.post(
            "/api/watches/import/apply",
            json={"version": 1, "rows": [{"address": ADDRESS, "groups": ["g"]}]},
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(create, range(12)))
    assert all(r.status_code in (200, 201) for r in responses)
    assert len(client.get("/api/watches").json()["watches"]) == 1
    assert len(client.get("/api/watches/collection-intent").json()["watches"]) == 1
    assert len(client.get("/api/groups").json()["groups"]) == 1


@pytest.mark.parametrize(
    "path,method,body,status",
    [
        ("/api/watches/not-a-uuid", "get", None, 422),
        (f"/api/watches/{uuid4()}", "get", None, 404),
        (f"/api/watches/{uuid4()}", "patch", {"state": "paused"}, 404),
        (f"/api/watches/{uuid4()}", "delete", None, 404),
        (f"/api/groups/{uuid4()}", "patch", {"name": "new"}, 404),
        ("/api/watches", "post", {"address": "1" * 32, "chain": "ethereum"}, 422),
        ("/api/watches", "post", {"address": "PRIVATE_INVALID"}, 422),
        ("/api/groups", "post", {"name": " "}, 422),
        ("/api/watches/import/apply", "post", {"version": 2, "rows": []}, 422),
        ("/api/watches/import/preview", "post", {"version": 1, "rows": [{}] * 1001}, 422),
    ],
)
def test_clear_private_error_responses(client, path, method, body, status):
    kwargs = {"json": body} if body is not None else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == status and "detail" in response.json()
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE_INVALID" not in response.text


def test_mutations_require_json_and_never_enable_cross_origin_access(client):
    for headers in ({}, {"content-type": "text/plain"}):
        response = client.post(
            "/api/watches", content='{"address":"' + SECOND + '"}', headers=headers
        )
        assert response.status_code == 415
    response = client.options(
        "/api/watches",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    assert client.get("/api/watches").json()["watches"] == []


def test_25_row_initial_batch_and_case_sensitive_identity(client, database):
    # Controlled 32-byte encodings, not an operator's chosen wallets or live captures.
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    rows = [
        {"address": "1" * 31 + c, "groups": ["initial"], "state": "paused"} for c in alphabet[1:26]
    ]
    batch = {"version": 1, "rows": rows}
    preview = client.post("/api/watches/import/preview", json=batch)
    assert preview.json()["counts"] == {"valid": 25, "duplicate": 0, "invalid": 0}
    assert client.get("/api/watches").json()["watches"] == []
    assert client.post("/api/watches/import/apply", json=batch).status_code == 200
    with TestClient(create_app(database)) as restarted:
        assert len(restarted.get("/api/watches").json()["watches"]) == 25
        assert restarted.get("/api/watches/collection-intent").json()["watches"] == []
    assert client.post("/api/watches", json={"address": "1" * 31 + "a"}).status_code == 201
    assert client.post("/api/watches", json={"address": "1" * 31 + "A"}).status_code == 200
    assert len(client.get("/api/watches").json()["watches"]) == 26


def test_commit_failure_is_not_reported_as_success(client, database):
    async def deferred_failure():
        async with transaction(database) as store:
            await store.connection.execute(
                """
                CREATE FUNCTION reject_watch_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'PRIVATE_COMMIT_SECRET'; END $$;
                CREATE CONSTRAINT TRIGGER reject_watch_commit AFTER INSERT ON watches
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_watch_commit();
            """,
                prepare=False,
            )

    asyncio.run(deferred_failure())
    response = client.post("/api/watches", json={"address": ADDRESS})
    assert response.status_code == 503 and "PRIVATE_COMMIT_SECRET" not in response.text
    assert client.get("/api/watches").json()["watches"] == []


def test_export_reimports_into_an_empty_watchlist(client, database):
    add(client, alias="manual", note="private", groups=["group"], state="paused")
    exported = client.get("/api/watches/export").json()

    async def empty_test_schema():
        # This test owns a random schema created by the database fixture.
        async with transaction(database) as store:
            await store.connection.execute("DELETE FROM watches")
            await store.connection.execute("DELETE FROM watch_groups")
            await store.connection.execute("DELETE FROM wallets")

    asyncio.run(empty_test_schema())
    assert client.get("/api/watches").json()["watches"] == []
    response = client.post("/api/watches/import/apply", json=exported)
    assert response.status_code == 200
    assert response.json()["counts"] == {"valid": 1, "duplicate": 0, "invalid": 0}
    assert client.get("/api/watches/export").json() == exported
