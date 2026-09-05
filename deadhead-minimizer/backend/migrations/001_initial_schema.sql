-- =====================================================================
-- Dynamic Deadhead Minimizer — Initial Schema
-- Target: PostgreSQL 15+ with PostGIS 3.3+
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE equipment_type_enum AS ENUM ('van', 'reefer', 'flatbed', 'stepdeck', 'power_only');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE truck_status_enum AS ENUM ('available', 'in_transit', 'booked', 'off_duty');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE load_status_enum AS ENUM ('posted', 'negotiating', 'booked', 'expired', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE zone_classification_enum AS ENUM ('hot', 'balanced', 'soft', 'dead');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------
-- TABLE: kma_heatmaps
-- One row per Key Market Area (DAT's ~135 US/Canada freight markets).
-- Refreshed on ingestion cadence (e.g. every 15 min) via the DAT pipeline.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kma_heatmaps (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kma_code            VARCHAR(10) NOT NULL,           -- e.g. 'ATL', 'CHI'
    kma_name            VARCHAR(120) NOT NULL,          -- e.g. 'Atlanta, GA'
    zip3                VARCHAR(3) NOT NULL,            -- representative 3-digit zip cluster
    equipment_type      equipment_type_enum NOT NULL,   -- ratios are equipment-specific
    centroid            GEOGRAPHY(Point, 4326) NOT NULL,
    geom                GEOMETRY(Polygon, 4326),        -- KMA boundary for map rendering (nullable until geocoded)
    load_count          INTEGER NOT NULL DEFAULT 0,
    truck_count         INTEGER NOT NULL DEFAULT 0,
    load_to_truck_ratio NUMERIC(6, 2) NOT NULL DEFAULT 0,
    avg_outbound_rpm    NUMERIC(6, 2),                  -- avg $/mile leaving this KMA
    avg_inbound_rpm     NUMERIC(6, 2),                  -- avg $/mile arriving into this KMA
    zone_classification zone_classification_enum NOT NULL DEFAULT 'balanced',
    source               VARCHAR(30) NOT NULL DEFAULT 'dat_api', -- 'dat_api' | 'extension_bridge'
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kma_code, equipment_type)
);

CREATE INDEX IF NOT EXISTS idx_kma_centroid_gist ON kma_heatmaps USING GIST (centroid);
CREATE INDEX IF NOT EXISTS idx_kma_geom_gist ON kma_heatmaps USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_kma_code ON kma_heatmaps (kma_code);
CREATE INDEX IF NOT EXISTS idx_kma_zone_class ON kma_heatmaps (zone_classification);

-- ---------------------------------------------------------------------
-- TABLE: loads
-- DAT load board postings (or extension-bridge scraped equivalents).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loads (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dat_reference_id    VARCHAR(64) UNIQUE,             -- external DAT posting ID, null if scraped-only

    origin_city         VARCHAR(80) NOT NULL,
    origin_state        VARCHAR(2) NOT NULL,
    origin_zip3         VARCHAR(3) NOT NULL,
    origin_geom         GEOGRAPHY(Point, 4326) NOT NULL,
    origin_kma_code     VARCHAR(10) REFERENCES kma_heatmaps (kma_code),

    dest_city           VARCHAR(80) NOT NULL,
    dest_state          VARCHAR(2) NOT NULL,
    dest_zip3           VARCHAR(3) NOT NULL,
    dest_geom           GEOGRAPHY(Point, 4326) NOT NULL,
    dest_kma_code       VARCHAR(10) REFERENCES kma_heatmaps (kma_code),

    equipment_type      equipment_type_enum NOT NULL,
    miles               NUMERIC(7, 1) NOT NULL,
    rate_total_usd       NUMERIC(9, 2),                  -- null until negotiated/confirmed
    rpm_usd              NUMERIC(6, 2),                   -- rate_total / miles, denormalized for fast sort
    weight_lbs           INTEGER,

    broker_company       VARCHAR(120),
    broker_contact_name  VARCHAR(120),
    broker_phone         VARCHAR(20),
    broker_mc_number     VARCHAR(20),
    broker_email         VARCHAR(120),

    pickup_date          DATE NOT NULL,
    delivery_date        DATE NOT NULL,
    status                load_status_enum NOT NULL DEFAULT 'posted',

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_loads_origin_geom_gist ON loads USING GIST (origin_geom);
CREATE INDEX IF NOT EXISTS idx_loads_dest_geom_gist ON loads USING GIST (dest_geom);
CREATE INDEX IF NOT EXISTS idx_loads_status ON loads (status);
CREATE INDEX IF NOT EXISTS idx_loads_equipment ON loads (equipment_type);
CREATE INDEX IF NOT EXISTS idx_loads_delivery_date ON loads (delivery_date);
CREATE INDEX IF NOT EXISTS idx_loads_dest_kma ON loads (dest_kma_code);

-- ---------------------------------------------------------------------
-- TABLE: trucks
-- Active driver/asset positions and status, used to compute truck_count
-- per KMA and to know where the deadhead calculation starts from.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trucks (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_name           VARCHAR(120) NOT NULL,
    truck_number           VARCHAR(30),
    equipment_type          equipment_type_enum NOT NULL,

    current_geom            GEOGRAPHY(Point, 4326) NOT NULL,
    current_city             VARCHAR(80),
    current_state             VARCHAR(2),
    current_kma_code           VARCHAR(10) REFERENCES kma_heatmaps (kma_code),

    status                      truck_status_enum NOT NULL DEFAULT 'available',
    target_destination_city      VARCHAR(80),
    target_destination_state      VARCHAR(2),
    available_from_date            DATE,

    assigned_load_id                 UUID REFERENCES loads (id) ON DELETE SET NULL,

    updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trucks_current_geom_gist ON trucks USING GIST (current_geom);
CREATE INDEX IF NOT EXISTS idx_trucks_status ON trucks (status);
CREATE INDEX IF NOT EXISTS idx_trucks_kma ON trucks (current_kma_code);

-- ---------------------------------------------------------------------
-- Trigger: keep updated_at fresh on row modification
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_loads_updated_at ON loads;
CREATE TRIGGER trg_loads_updated_at BEFORE UPDATE ON loads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_trucks_updated_at ON trucks;
CREATE TRIGGER trg_trucks_updated_at BEFORE UPDATE ON trucks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_kma_updated_at ON kma_heatmaps;
CREATE TRIGGER trg_kma_updated_at BEFORE UPDATE ON kma_heatmaps
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
