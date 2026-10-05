"""Real PostgreSQL transaction/concurrency checks; no network provider calls."""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from wallet_observer.db import transaction
from wallet_observer.db.delivery import dispatch_batch, read_delivery
from wallet_observer.db.jobs import LeaseLost, claim, enqueue, finish
from wallet_observer.db.migrations import MigrationError, migrate, migration_files
from wallet_observer.db.models import CanonicalEvent, ExecutionLeg
from wallet_observer.db.store import CheckpointConflict, RevisionConflict

FIXTURES = Path(__file__).parents[1] / "fixtures" / "solana"


def buy_fixture():
    fixture = json.loads((FIXTURES / "buy.json").read_text())
    payload, expected = fixture["payload"], fixture["expected"]
    instruction = next(
        i for i in payload["parsed"]["instructions"] if i["instructionName"] == "buy_exact_quote_in"
    )
    summary = instruction["summary"]["parsedData"]
    # Hand-reviewed storage input, NOT a production provider normalizer.
    # Owner balance deltas include fees; the watched account is not this buyer.
    deltas = [int(b["post_raw"]) - int(b["pre_raw"]) for b in expected["balance_checks"]]
    event = CanonicalEvent(
        chain="solana",
        transaction_id=payload["signature"],
        instruction_index=instruction["instructionIndex"],
        wallet_address=expected["actor"],
        occurred_at=datetime.fromtimestamp(payload["parsed"]["blockTime"], UTC),
        kind=expected["classification"],
        chain_confirmation=expected["chain_confirmation"],
        execution_status="succeeded",
        legs=(
            ExecutionLeg(
                token_address=summary["output_mint"],
                direction="in",
                raw_quantity=deltas[0],
                token_decimals=6,
            ),
            ExecutionLeg(
                token_address=summary["input_mint"],
                direction="out",
                raw_quantity=-deltas[1],
                token_decimals=9,
            ),
        ),
    )
    return payload, event


async def persist(store, *, event=None, source_key=None):
    payload, fixture_event = buy_fixture()
    event = event or fixture_event
    source = await store.source_record(
        provider="helius",
        chain=event.chain,
        source_event_id=source_key or event.transaction_id,
        payload=payload,
        replay=event.replay,
    )
    return await store.write_event(source, event, expected_revision=0)


async def count(store, table):
    # Table names are constants in tests, never user/provider input.
    return (await store.one(f"SELECT count(*) AS n FROM {table}"))["n"]


def test_empty_migration_and_upgrade_preserve_data(empty_database):
    async def check():
        assert await migrate(empty_database, target=1) == [1]
        async with transaction(empty_database) as store:
            wallet = await store.wallet("solana", "CasePreserved")
        assert await migrate(empty_database) == [2]
        assert await migrate(empty_database) == []
        async with transaction(empty_database) as store:
            assert await store.wallet("solana", "CasePreserved") == wallet
            names = await (
                await store.connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                )
            ).fetchall()
            tables = {r["tablename"] for r in names}
            assert {"durable_jobs", "notification_outbox", "source_checkpoints"} <= tables
            assert not tables & {"users", "billing", "entitlements", "quotas", "sessions"}

    asyncio.run(check())


def test_migrations_are_atomic_and_detect_tampering(database, tmp_path):
    async def check():
        for _, name, _, text in migration_files():
            (tmp_path / name).write_text(text)
        (tmp_path / "0003_broken.sql").write_text(
            "CREATE TABLE should_rollback (id integer); SELECT missing_migration_function();"
        )
        with pytest.raises(psycopg.Error):
            await migrate(database, directory=tmp_path)
        async with transaction(database) as store:
            assert (await store.one("SELECT to_regclass('should_rollback') AS value"))[
                "value"
            ] is None
            assert await count(store, "schema_migrations") == 2
        (tmp_path / "0001_canonical.sql").write_text("SELECT 1;")
        with pytest.raises(MigrationError, match="differ"):
            await migrate(database, directory=tmp_path)
        with pytest.raises(MigrationError, match="Downgrades"):
            await migrate(database, target=1)

    asyncio.run(check())


def test_concurrent_migration_is_serialized(empty_database):
    async def check():
        results = await asyncio.gather(migrate(empty_database), migrate(empty_database))
        assert sorted(results, key=len) == [[], [1, 2]]

    asyncio.run(check())


def test_duplicate_fixture_ingestion_is_idempotent(database):
    async def check():
        async with transaction(database) as store:
            first = await persist(store)
        async with transaction(database) as store:
            _, draft = buy_fixture()
            assert await persist(store, event=draft.model_copy(update={"replay": True})) == first
            assert await count(store, "raw_source_events") == 1
            assert await count(store, "source_payloads") == 1
            assert await count(store, "executions") == 1
            assert await count(store, "event_revisions") == 1
            assert await count(store, "publication_outbox") == 1
            amounts = await (
                await store.connection.execute(
                    "SELECT raw_quantity FROM execution_legs ORDER BY leg_index"
                )
            ).fetchall()
            assert [r["raw_quantity"] for r in amounts] == [Decimal(7203337007), Decimal(70000000)]
        assert await dispatch_batch(database) == 1
        assert await dispatch_batch(database) == 1

    asyncio.run(check())


def test_real_stream_and_history_overlap_share_source_identity(database):
    fixture = json.loads((FIXTURES / "overlap-duplicate.json").read_text())

    async def check():
        async with transaction(database) as store:
            ids = []
            for payload in [fixture["payload"], fixture["stream_payload"], fixture["payload"]]:
                ids.append(
                    await store.source_record(
                        provider="helius",
                        chain="solana",
                        source_event_id=fixture["payload"]["signature"],
                        payload=payload,
                    )
                )
            assert len(set(ids)) == 1
            assert await count(store, "source_payloads") == 2
            assert await count(store, "executions") == 0  # Persistence never infers a trade.

    asyncio.run(check())


def test_same_amount_distinct_execution_identities(database):
    async def check():
        _, base = buy_fixture()
        # Controlled canonical identity variants, not fabricated provider fixtures.
        variants = [
            base,
            base.model_copy(update={"transaction_id": "Storage-test-second-tx"}),
            base.model_copy(update={"inner_instruction_index": 0}),
        ]
        async with transaction(database) as store:
            results = [await persist(store, event=e) for e in variants]
            assert len({r[0] for r in results}) == 3
            assert await count(store, "executions") == 3

    asyncio.run(check())


def test_rollback_preserves_checkpoint_and_has_no_phantom_event(database):
    async def check():
        checkpoint = dict(provider="helius", chain="solana", scope="test-wallet")
        async with transaction(database) as store:
            await store.advance_checkpoint(**checkpoint, safe_slot=100, expected_version=0)
        with pytest.raises(RuntimeError, match="crash"):
            async with transaction(database) as store:
                await persist(store)
                await enqueue(store, kind="normalize", object_key="test", payload={})
                await store.advance_checkpoint(**checkpoint, safe_slot=101, expected_version=1)
                raise RuntimeError("crash before commit")
        async with transaction(database) as store:
            row = await store.one("SELECT safe_slot, version FROM source_checkpoints")
            assert row == {"safe_slot": 100, "version": 1}
            for table in [
                "raw_source_events",
                "canonical_events",
                "event_revisions",
                "executions",
                "publication_outbox",
                "durable_jobs",
            ]:
                assert await count(store, table) == 0
        assert await dispatch_batch(database) == 0

    asyncio.run(check())


def test_checkpoint_cas_rejects_stale_or_regressing_batch(database):
    async def check():
        key = dict(provider="helius", chain="solana", scope="test")
        async with transaction(database) as store:
            await store.advance_checkpoint(**key, safe_slot=100, expected_version=0)
        for slot, version in [(101, 0), (99, 1)]:
            with pytest.raises(CheckpointConflict):
                async with transaction(database) as store:
                    await persist(store)
                    await store.advance_checkpoint(**key, safe_slot=slot, expected_version=version)
        async with transaction(database) as store:
            assert await count(store, "executions") == 0

    asyncio.run(check())


def test_precision_address_case_and_chain_round_trip(database):
    async def check():
        _, base = buy_fixture()
        quantity = Decimal("9" * 78)
        usd = Decimal("12345678901234567890.12345678901234567890123456789")
        leg = base.legs[0].model_copy(update={"raw_quantity": quantity, "token_address": "MintAbC"})
        event = base.model_copy(update={"execution_usd": usd, "legs": (leg, base.legs[1])})
        async with transaction(database) as store:
            await persist(store, event=event)
            tokens = [
                await store.token(c, a)
                for c, a in [
                    ("solana", "MintAbC"),
                    ("solana", "mintabc"),
                    ("test-chain", "MintAbC"),
                ]
            ]
            assert len(set(tokens)) == 3
            values = await store.one("""
                SELECT e.execution_usd, l.raw_quantity, t.address, t.chain FROM executions e
                JOIN execution_legs l ON l.execution_id = e.id JOIN tokens t ON t.id = l.token_id
                WHERE l.leg_index = 0
            """)
            assert values == {
                "execution_usd": usd,
                "raw_quantity": quantity,
                "address": "MintAbC",
                "chain": "solana",
            }
            snapshot = (await store.one("SELECT payload FROM event_revisions"))["payload"]
            assert Decimal(snapshot["legs"][0]["raw_quantity"]) == quantity
            assert Decimal(snapshot["execution_usd"]) == usd
            assert snapshot["source_order_status"] is None
            assert snapshot["coverage_status"] == "partial"

    asyncio.run(check())


@pytest.mark.parametrize("bad", ["1.5", "-1", "NaN", "Infinity", "1e78"])
def test_database_rejects_fractional_or_invalid_raw_amounts(database, bad):
    async def check():
        async with transaction(database) as store:
            await persist(store)
        with pytest.raises(psycopg.errors.CheckViolation):
            async with transaction(database) as store:
                await store.connection.execute(
                    "UPDATE execution_legs SET raw_quantity = %s", (bad,)
                )

    asyncio.run(check())


def test_revision_correction_is_atomic_and_snapshots_are_immutable(database):
    async def check():
        payload, event = buy_fixture()
        async with transaction(database) as store:
            event_id, _ = await persist(store)
        failed = event.model_copy(
            update={
                "kind": "transaction.failed",
                "execution_status": "reverted",
                "chain_confirmation": "orphaned",
            }
        )
        async with transaction(database) as store:
            source = await store.source_record(
                provider="helius",
                chain="solana",
                source_event_id=event.transaction_id,
                payload=payload,
            )
            assert await store.write_event(source, failed, expected_revision=1) == (event_id, 2)
            assert (await store.one("SELECT status FROM executions"))["status"] == "reverted"
        with pytest.raises(RevisionConflict):
            async with transaction(database) as store:
                await store.write_event(source, event, expected_revision=1)
        with pytest.raises(psycopg.Error):
            async with transaction(database) as store:
                await store.connection.execute("DELETE FROM event_revisions")
        assert await dispatch_batch(database) == 2
        async with transaction(database) as store:
            page = await read_delivery(store)
            assert [r["payload"]["execution_status"] for r in page["events"]] == [
                "succeeded",
                "reverted",
            ]

    asyncio.run(check())


def test_late_commit_with_earlier_outbox_id_is_delivered(database):
    async def check():
        _, base = buy_fixture()
        async with transaction(database) as store:
            await store.wallet(base.chain, base.wallet_address)
            for leg in base.legs:
                await store.token(base.chain, leg.token_address)
        async with transaction(database) as slow:
            first, _ = await persist(slow)
            async with transaction(database) as fast:
                second, _ = await persist(
                    fast,
                    event=base.model_copy(update={"transaction_id": "Storage-test-faster-commit"}),
                )
            assert await dispatch_batch(database) == 1
            async with transaction(database) as reader:
                assert (await read_delivery(reader))["events"][0]["event_id"] == second
        assert await dispatch_batch(database) == 2
        async with transaction(database) as reader:
            assert (await read_delivery(reader, after=1))["events"][0]["event_id"] == first

    asyncio.run(check())


def test_dispatcher_concurrency_and_rollback(database):
    async def check():
        async with transaction(database) as store:
            await persist(store)
            # Fault injection at the delivery write; all dispatcher changes must roll back.
            await store.connection.execute("""
                CREATE FUNCTION fail_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected_failure'; END; $$;
                CREATE TRIGGER fail_delivery BEFORE INSERT ON delivery_log
                    FOR EACH ROW EXECUTE FUNCTION fail_delivery();
            """)
        with pytest.raises(psycopg.Error):
            await dispatch_batch(database)
        async with transaction(database) as store:
            assert (await store.one("SELECT committed_position FROM delivery_state"))[
                "committed_position"
            ] == 0
            assert (await store.one("SELECT dispatched_at FROM publication_outbox"))[
                "dispatched_at"
            ] is None
            await store.connection.execute("DROP TRIGGER fail_delivery ON delivery_log")
        assert await asyncio.gather(dispatch_batch(database), dispatch_batch(database)) == [1, 1]
        async with transaction(database) as store:
            assert await count(store, "delivery_log") == 1

    asyncio.run(check())


def test_job_claim_crash_reclaim_and_fenced_completion(database):
    async def check():
        async with transaction(database) as store:
            job_id = await enqueue(store, kind="normalize", object_key="one", payload={})
            assert await enqueue(store, kind="normalize", object_key="one", payload={}) == job_id
        async with transaction(database) as a:
            old = await claim(a, kind="normalize")
            async with transaction(database) as b:
                assert await claim(b, kind="normalize") is None
        # Simulate an expired lease without sleeping or weakening production lease checks.
        async with transaction(database) as store:
            await store.connection.execute(
                "UPDATE durable_jobs SET lease_until = clock_timestamp() - interval '1 second'"
            )
        async with transaction(database) as store:
            new = await claim(store, kind="normalize")
            assert new["id"] == old["id"] and new["attempts"] == 2
            assert new["lease_token"] != old["lease_token"]
        with pytest.raises(LeaseLost):
            async with transaction(database) as store:
                await finish(store, job_id=job_id, lease_token=old["lease_token"])
        async with transaction(database) as store:
            assert await finish(store, job_id=job_id, lease_token=new["lease_token"]) == "completed"
        async with transaction(database) as store:
            assert await claim(store, kind="normalize") is None

    asyncio.run(check())


def test_jobs_exhaust_attempts_and_bound_retries(database):
    async def check():
        async with transaction(database) as store:
            await enqueue(store, kind="normalize", object_key="retry", payload={}, max_attempts=2)
        for expected in ["pending", "failed"]:
            async with transaction(database) as store:
                job = await claim(store, kind="normalize")
                assert (
                    await finish(
                        store,
                        job_id=job["id"],
                        lease_token=job["lease_token"],
                        error_code="source_unavailable",
                        retry_seconds=0,
                    )
                    == expected
                )
        async with transaction(database) as store:
            await enqueue(store, kind="normalize", object_key="dies", payload={}, max_attempts=1)
            await claim(store, kind="normalize")
        async with transaction(database) as store:
            await store.connection.execute(
                "UPDATE durable_jobs SET lease_until = clock_timestamp() - interval '1 second' "
                "WHERE status = 'running'"
            )
        async with transaction(database) as store:
            assert await claim(store, kind="normalize") is None
            assert await count(store, "durable_jobs WHERE status = 'failed'") == 2

    asyncio.run(check())


def test_payload_expiry_retains_identity_and_notification_intent_is_unique(database):
    async def check():
        async with transaction(database) as store:
            event_id, _ = await persist(store)
            job = await enqueue(store, kind="telegram", object_key=str(event_id), payload={})
            for _ in range(2):
                await store.connection.execute(
                    """
                    INSERT INTO notification_outbox (event_id, destination_key, job_id, expires_at)
                    VALUES (%s, 'primary', %s, clock_timestamp() + interval '1 hour')
                    ON CONFLICT (event_id, destination_key) DO NOTHING
                """,
                    (event_id, job),
                )
            await store.connection.execute("""
                UPDATE source_payloads SET received_at = clock_timestamp() - interval '2 days',
                    expires_at = clock_timestamp() - interval '1 day'
            """)
            assert await store.expire_payloads(limit=1) == 1
            assert await count(store, "raw_source_events") == 1
            assert await count(store, "executions") == 1
            assert await count(store, "notification_outbox") == 1
        async with transaction(database) as store:
            await persist(store)
            assert await count(store, "executions") == 1

    asyncio.run(check())


def test_disconnected_producer_rolls_back_all_work(database):
    async def check():
        with pytest.raises(psycopg.Error):
            async with transaction(database) as producer:
                await persist(producer)
                await producer.advance_checkpoint(
                    provider="helius", chain="solana", scope="test", safe_slot=1, expected_version=0
                )
                pid = (await producer.one("SELECT pg_backend_pid() AS pid"))["pid"]
                async with transaction(database) as killer:
                    await killer.connection.execute("SELECT pg_terminate_backend(%s)", (pid,))
                await producer.connection.execute("SELECT 1")
        async with transaction(database) as reader:
            assert await count(reader, "canonical_events") == 0
            assert await count(reader, "source_checkpoints") == 0
            assert await count(reader, "publication_outbox") == 0
        assert await dispatch_batch(database) == 0

    asyncio.run(check())


def test_delivery_page_cursor_does_not_skip_unread_rows(database):
    async def check():
        _, base = buy_fixture()
        async with transaction(database) as store:
            for index in range(3):
                await persist(store, event=base.model_copy(update={"instruction_index": index}))
        assert await dispatch_batch(database) == 3
        async with transaction(database) as store:
            page = await read_delivery(store, limit=1)
            assert page["committed_position"] == 3 and page["next_cursor"] == 1
            next_page = await read_delivery(store, after=page["next_cursor"], limit=1)
            assert next_page["next_cursor"] == 2
            empty = await read_delivery(store, after=3)
            assert empty == {"events": [], "next_cursor": 3, "committed_position": 3}
            with pytest.raises(ValueError, match="ahead"):
                await read_delivery(store, after=4)

    asyncio.run(check())


def test_cross_chain_event_source_is_rejected(database):
    async def check():
        payload, event = buy_fixture()
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            async with transaction(database) as store:
                source = await store.source_record(
                    provider="test",
                    chain="different-chain",
                    source_event_id="test",
                    payload=payload,
                )
                await store.write_event(source, event, expected_revision=0)
        async with transaction(database) as store:
            assert await count(store, "executions") == 0

    asyncio.run(check())


def test_equivalent_decimal_encodings_do_not_create_revisions(database):
    async def check():
        _, base = buy_fixture()
        first = base.model_copy(update={"execution_usd": Decimal("12.5000")})
        second = base.model_copy(
            update={
                "execution_usd": Decimal("12.5"),
                "legs": (
                    base.legs[0].model_copy(
                        update={"raw_quantity": Decimal(str(base.legs[0].raw_quantity) + ".00")}
                    ),
                    base.legs[1],
                ),
            }
        )
        async with transaction(database) as store:
            result = await persist(store, event=first)
        async with transaction(database) as store:
            assert await persist(store, event=second) == result
            assert await count(store, "event_revisions") == 1

    asyncio.run(check())
