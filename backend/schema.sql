-- Reference schema for PostgreSQL.  The application also creates these
-- tables automatically via SQLAlchemy on startup; this file is the
-- human-readable DDL of record (原始指标 / 单位 / 权重来源 / 决策版).

CREATE TABLE IF NOT EXISTS scenarios (
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(64) UNIQUE NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions (
    id          SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    settings    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS criteria (
    id          SERIAL PRIMARY KEY,
    decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    key         VARCHAR(64) NOT NULL,
    label       VARCHAR(200) NOT NULL,
    unit        VARCHAR(64) NOT NULL DEFAULT '',
    kind        VARCHAR(16) NOT NULL CHECK (kind IN ('benefit','cost','target')),
    target_low  DOUBLE PRECISION,
    target_high DOUBLE PRECISION,
    fixed_min   DOUBLE PRECISION,
    fixed_max   DOUBLE PRECISION,
    UNIQUE (decision_id, key)
);

CREATE TABLE IF NOT EXISTS alternatives (
    id          SERIAL PRIMARY KEY,
    decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    key         VARCHAR(64) NOT NULL,
    label       VARCHAR(200) NOT NULL,
    UNIQUE (decision_id, key)
);

CREATE TABLE IF NOT EXISTS metric_values (
    id             SERIAL PRIMARY KEY,
    alternative_id INTEGER NOT NULL REFERENCES alternatives(id) ON DELETE CASCADE,
    criterion_id   INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    value          DOUBLE PRECISION,   -- NULL = genuinely missing, never 0
    note           VARCHAR(300) NOT NULL DEFAULT '',
    UNIQUE (alternative_id, criterion_id)
);

CREATE TABLE IF NOT EXISTS weight_sets (
    id          SERIAL PRIMARY KEY,
    decision_id INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    method      VARCHAR(32) NOT NULL CHECK (method IN ('manual','entropy','critic')),
    source      TEXT NOT NULL DEFAULT '',   -- mandatory justification for manual sets
    weights     JSONB NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decision_versions (
    id            SERIAL PRIMARY KEY,
    decision_id   INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    weight_set_id INTEGER REFERENCES weight_sets(id),
    label         VARCHAR(200) NOT NULL,
    method        VARCHAR(32) NOT NULL CHECK (method IN ('wsm','topsis')),
    snapshot      JSONB NOT NULL,           -- immutable full audit snapshot
    created_by    VARCHAR(120) NOT NULL DEFAULT 'committee',
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_values_alt ON metric_values(alternative_id);
CREATE INDEX IF NOT EXISTS idx_values_crit ON metric_values(criterion_id);
