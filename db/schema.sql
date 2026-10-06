-- 决策数据模型：原始指标 / 单位 / 候选 / 观测值 / 决策版本（快照）
CREATE TABLE IF NOT EXISTS criteria (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    unit        TEXT NOT NULL DEFAULT '',
    ctype       TEXT NOT NULL CHECK (ctype IN ('benefit','cost','target')),
    weight      DOUBLE PRECISION NOT NULL,
    source      TEXT NOT NULL DEFAULT 'manual',
    target_low  DOUBLE PRECISION,
    target_high DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS candidates (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS measurements (
    id            SERIAL PRIMARY KEY,
    candidate_id  INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    criterion_id  INTEGER NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    value         DOUBLE PRECISION,           -- NULL = 缺失，绝不自动当作满分
    UNIQUE (candidate_id, criterion_id)
);

CREATE TABLE IF NOT EXISTS decision_versions (
    id          SERIAL PRIMARY KEY,
    label       TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    options     JSONB NOT NULL,              -- 完整计算选项快照
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 决策版本对应的输入数据快照（保证历史版本可复算、不被后续编辑污染）
CREATE TABLE IF NOT EXISTS version_snapshots (
    version_id    INTEGER NOT NULL REFERENCES decision_versions(id) ON DELETE CASCADE,
    candidate_id  INTEGER NOT NULL,
    criterion_id  INTEGER NOT NULL,
    value         DOUBLE PRECISION,
    PRIMARY KEY (version_id, candidate_id, criterion_id)
);
