CREATE TABLE durable_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind ~ '^[a-z_]{1,64}$'),
    object_key text COLLATE "C" NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lease_token uuid, lease_until timestamptz,
    last_error_code text CHECK (last_error_code ~ '^[a-z_]{1,64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (attempts BETWEEN 0 AND max_attempts),
    CHECK ((status = 'running' AND lease_token IS NOT NULL AND lease_until IS NOT NULL)
        OR (status <> 'running' AND lease_token IS NULL AND lease_until IS NULL)),
    UNIQUE (kind, object_key)
);
CREATE INDEX claimable_job_idx ON durable_jobs (available_at, id) WHERE status = 'pending';
CREATE INDEX expired_job_idx ON durable_jobs (lease_until, id) WHERE status = 'running';
CREATE TABLE publication_outbox (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id uuid NOT NULL, revision integer NOT NULL,
    dispatched_at timestamptz,
    FOREIGN KEY (event_id, revision) REFERENCES event_revisions(event_id, revision),
    UNIQUE (event_id, revision)
);
CREATE INDEX pending_publication_idx ON publication_outbox(id) WHERE dispatched_at IS NULL;
CREATE TABLE delivery_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    committed_position bigint NOT NULL DEFAULT 0 CHECK (committed_position >= 0)
);
INSERT INTO delivery_state (singleton) VALUES (true);
CREATE TABLE delivery_log (
    position bigint PRIMARY KEY CHECK (position > 0),
    event_id uuid NOT NULL, revision integer NOT NULL,
    payload jsonb NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (event_id, revision) REFERENCES event_revisions(event_id, revision),
    UNIQUE (event_id, revision)
);
CREATE TABLE notification_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES canonical_events(id),
    destination_key text COLLATE "C" NOT NULL,
    job_id uuid NOT NULL UNIQUE REFERENCES durable_jobs(id),
    telegram_message_id text,
    expires_at timestamptz NOT NULL,
    UNIQUE (event_id, destination_key)
);

-- Every revision creates publication intent in the SAME transaction, even for future writers.
CREATE FUNCTION enqueue_event_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE canonical_events SET current_revision = NEW.revision
      WHERE id = NEW.event_id AND current_revision = NEW.revision - 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'noncontiguous_event_revision';
    END IF;
    INSERT INTO publication_outbox (event_id, revision) VALUES (NEW.event_id, NEW.revision);
    RETURN NEW;
END;
$$;
CREATE TRIGGER publish_revision AFTER INSERT ON event_revisions
    FOR EACH ROW EXECUTE FUNCTION enqueue_event_revision();

-- Revision snapshots are append-only. Corrections append another revision.
CREATE FUNCTION reject_revision_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'event_revisions_are_immutable';
END;
$$;
CREATE TRIGGER immutable_revisions BEFORE UPDATE OR DELETE ON event_revisions
    FOR EACH ROW EXECUTE FUNCTION reject_revision_mutation();

UPDATE canonical_events e SET current_revision = r.revision
FROM (SELECT event_id, max(revision) AS revision FROM event_revisions GROUP BY event_id) r
WHERE e.id = r.event_id;
INSERT INTO publication_outbox (event_id, revision)
SELECT event_id, revision FROM event_revisions ORDER BY event_id, revision;
