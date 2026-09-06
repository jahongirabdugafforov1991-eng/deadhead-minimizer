-- =====================================================================
-- System events — real activity log + savings tracker
-- =====================================================================

DO $$ BEGIN
    CREATE TYPE system_event_type_enum AS ENUM (
        'relocation_accepted', 'zone_shift', 'dead_zone_warning'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS system_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          system_event_type_enum NOT NULL,
    message              TEXT NOT NULL,          -- human-readable log line, e.g. "Truck #482 relocated ATL -> Chattanooga"

    kma_code               VARCHAR(10),
    deadhead_miles           NUMERIC(7, 1),          -- only set for relocation_accepted
    net_gain_usd               NUMERIC(9, 2),          -- only set for relocation_accepted

    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_events_created ON system_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events (event_type);
