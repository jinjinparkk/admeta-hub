-- admeta-hub 초기 스키마
-- 설계 문서: docs/CANONICAL_SCHEMA.md

CREATE EXTENSION IF NOT EXISTS vector;

-- ① Canonical 개념 마스터 (표준 사전) -------------------------------------
CREATE TABLE IF NOT EXISTS canonical_field (
    key         TEXT PRIMARY KEY,                    -- "CLICKS"
    kind        TEXT NOT NULL CHECK (kind IN ('metric','dimension','derived')),
    data_type   TEXT NOT NULL,
    unit        TEXT,
    description TEXT NOT NULL,
    formula     TEXT,                                -- derived 인 경우 계산식
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ③ 플랫폼 원천 필드 (문서에서 추출된 것) ---------------------------------
CREATE TABLE IF NOT EXISTS platform_field (
    id                    BIGSERIAL PRIMARY KEY,
    platform              TEXT NOT NULL,             -- "meta" | "google" | ...
    api_name              TEXT NOT NULL,             -- "metrics.cost_micros"
    display_name          TEXT,
    data_type             TEXT,
    category              TEXT,                      -- metric/dimension/segment/...
    raw_description       TEXT NOT NULL DEFAULT '',
    unit                  TEXT,
    source_url            TEXT,
    description_embedding vector(1024),              -- 설명 임베딩 (자연어 검색용)
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, api_name)
);

-- ④ Canonical ↔ 플랫폼 필드 매핑 (사람 검수 대상) -------------------------
CREATE TABLE IF NOT EXISTS field_mapping (
    id                 BIGSERIAL PRIMARY KEY,
    canonical_key      TEXT REFERENCES canonical_field(key),
    platform_field_id  BIGINT NOT NULL REFERENCES platform_field(id) ON DELETE CASCADE,
    transform          TEXT,                          -- "divide_by_million" 등
    extract_path       TEXT,                          -- 중첩 추출 경로
    confidence         REAL NOT NULL DEFAULT 1.0,
    reasoning          TEXT DEFAULT '',
    review_status      TEXT NOT NULL DEFAULT 'proposed'
                       CHECK (review_status IN ('proposed','approved','rejected','edited')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_key, platform_field_id)
);

-- 인덱스 -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_platform_field_platform ON platform_field(platform);
CREATE INDEX IF NOT EXISTS idx_field_mapping_canonical ON field_mapping(canonical_key);

-- 임베딩 근사 검색 인덱스 (cosine). 데이터가 쌓인 뒤 성능용.
CREATE INDEX IF NOT EXISTS idx_platform_field_embedding
    ON platform_field USING hnsw (description_embedding vector_cosine_ops);
