-- Storage identities are case-sensitive. Address validation belongs to chain adapters.
CREATE DOMAIN exact_raw_amount AS numeric
    CHECK (VALUE >= 0 AND VALUE < power(10::numeric, 78) AND VALUE = trunc(VALUE));
CREATE DOMAIN exact_value AS numeric
    CHECK (VALUE >= 0 AND VALUE < 'Infinity'::numeric);

CREATE TABLE wallets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chain text COLLATE "C" NOT NULL CHECK (chain ~ '^[a-z0-9][a-z0-9:_-]{0,63}$'),
    address text COLLATE "C" NOT NULL CHECK (length(address) BETWEEN 1 AND 200),
    UNIQUE (chain, address), UNIQUE (id, chain)
);
CREATE TABLE tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chain text COLLATE "C" NOT NULL CHECK (chain ~ '^[a-z0-9][a-z0-9:_-]{0,63}$'),
    address text COLLATE "C" NOT NULL CHECK (length(address) BETWEEN 1 AND 200),
    decimals smallint CHECK (decimals BETWEEN 0 AND 255),
    symbol text, name text,
    UNIQUE (chain, address), UNIQUE (id, chain)
);
CREATE TABLE watches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id uuid NOT NULL UNIQUE REFERENCES wallets(id),
    alias text, note text,
    state text NOT NULL DEFAULT 'paused'
        CHECK (state IN ('resolving', 'active', 'paused', 'unsupported', 'error', 'removed')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE watch_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL UNIQUE
);
CREATE TABLE watch_group_members (
    group_id uuid NOT NULL REFERENCES watch_groups(id) ON DELETE CASCADE,
    watch_id uuid NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, watch_id)
);
CREATE TABLE source_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL, source_identity_id text COLLATE "C" NOT NULL,
    display_name text, UNIQUE (provider, source_identity_id)
);
CREATE TABLE identity_wallet_links (
    identity_id uuid NOT NULL REFERENCES source_identities(id),
    wallet_id uuid NOT NULL REFERENCES wallets(id),
    evidence_type text NOT NULL, evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    verified_at timestamptz NOT NULL,
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (identity_id, wallet_id)
);

-- Keep the deduplication envelope after expiring potentially large private payloads.
CREATE TABLE raw_source_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL, chain text COLLATE "C" NOT NULL,
    source_event_id text COLLATE "C" NOT NULL,
    occurred_at timestamptz,
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    processing_state text NOT NULL DEFAULT 'pending'
        CHECK (processing_state IN ('pending', 'processed', 'quarantined')),
    error_code text CHECK (error_code ~ '^[a-z_]{1,64}$'),
    UNIQUE (provider, chain, source_event_id), UNIQUE (id, chain)
);
CREATE TABLE source_payloads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_record_id uuid NOT NULL REFERENCES raw_source_events(id),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    replay boolean NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    CHECK (expires_at > received_at),
    UNIQUE (source_record_id, payload_sha256)
);
CREATE INDEX source_payload_expiry_idx ON source_payloads (expires_at, id);

CREATE TABLE canonical_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chain text COLLATE "C" NOT NULL,
    transaction_id text COLLATE "C" NOT NULL CHECK (length(transaction_id) > 0),
    instruction_index integer NOT NULL CHECK (instruction_index >= 0),
    inner_instruction_index integer CHECK (inner_instruction_index >= 0),
    wallet_id uuid NOT NULL,
    occurred_at timestamptz,
    current_revision integer NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (wallet_id, chain) REFERENCES wallets(id, chain),
    UNIQUE NULLS NOT DISTINCT
        (chain, transaction_id, instruction_index, inner_instruction_index, wallet_id),
    UNIQUE (id, chain)
);
CREATE INDEX event_wallet_time_idx ON canonical_events (wallet_id, occurred_at DESC, id);
CREATE INDEX event_transaction_idx ON canonical_events (chain, transaction_id);
CREATE TABLE event_sources (
    event_id uuid NOT NULL, source_record_id uuid NOT NULL, chain text COLLATE "C" NOT NULL,
    FOREIGN KEY (event_id, chain) REFERENCES canonical_events(id, chain),
    FOREIGN KEY (source_record_id, chain) REFERENCES raw_source_events(id, chain),
    PRIMARY KEY (event_id, source_record_id)
);
CREATE TABLE event_revisions (
    event_id uuid NOT NULL REFERENCES canonical_events(id),
    revision integer NOT NULL CHECK (revision > 0),
    kind text NOT NULL CHECK (kind IN
        ('trade.buy', 'trade.sell', 'trade.swap', 'transfer', 'unknown', 'unknown.swap', 'transaction.failed')),
    chain_confirmation text NOT NULL CHECK (chain_confirmation IN
        ('unknown', 'observed', 'confirmed', 'finalized', 'orphaned')),
    source_order_status text,
    coverage_status text NOT NULL CHECK (coverage_status IN ('unknown', 'partial', 'complete')),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (event_id, revision)
);
CREATE TABLE executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL UNIQUE, chain text COLLATE "C" NOT NULL,
    status text NOT NULL CHECK (status IN ('succeeded', 'failed', 'reverted', 'unknown')),
    execution_usd exact_value,
    valuation_status text NOT NULL CHECK (valuation_status IN ('unavailable', 'known')),
    CHECK ((valuation_status = 'known') = (execution_usd IS NOT NULL)),
    FOREIGN KEY (event_id, chain) REFERENCES canonical_events(id, chain),
    UNIQUE (id, chain)
);
CREATE TABLE execution_legs (
    execution_id uuid NOT NULL, chain text COLLATE "C" NOT NULL,
    leg_index integer NOT NULL CHECK (leg_index >= 0),
    token_id uuid NOT NULL, direction text NOT NULL CHECK (direction IN ('in', 'out', 'fee')),
    raw_quantity exact_raw_amount NOT NULL,
    token_decimals smallint NOT NULL CHECK (token_decimals BETWEEN 0 AND 255),
    FOREIGN KEY (execution_id, chain) REFERENCES executions(id, chain),
    FOREIGN KEY (token_id, chain) REFERENCES tokens(id, chain),
    PRIMARY KEY (execution_id, leg_index)
);
CREATE INDEX execution_token_idx ON execution_legs (token_id, execution_id);
CREATE TABLE token_quotes (
    token_id uuid NOT NULL REFERENCES tokens(id), provider text NOT NULL,
    observed_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
    price_usd exact_value,
    status text NOT NULL CHECK (status IN ('available', 'unavailable')),
    CHECK ((status = 'available') = (price_usd IS NOT NULL)),
    CHECK (expires_at > observed_at),
    PRIMARY KEY (token_id, provider, observed_at)
);
CREATE TABLE source_checkpoints (
    provider text NOT NULL, chain text COLLATE "C" NOT NULL, scope text COLLATE "C" NOT NULL,
    safe_slot bigint CHECK (safe_slot >= 0), cursor jsonb,
    version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (provider, chain, scope)
);
CREATE TABLE coverage_gaps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL, chain text COLLATE "C" NOT NULL, scope text COLLATE "C" NOT NULL,
    from_slot bigint NOT NULL CHECK (from_slot >= 0),
    to_slot bigint NOT NULL CHECK (to_slot >= from_slot),
    reason_code text NOT NULL CHECK (reason_code ~ '^[a-z_]{1,64}$'),
    resolved_at timestamptz,
    UNIQUE (provider, chain, scope, from_slot, to_slot, reason_code)
);
