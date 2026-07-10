"""SQLite 저장소 — 크롤·추출·매핑 결과를 담는 정리된 DB.

주 1회 자동 실행이 목표라 설정 0인 SQLite로 시작한다(파일 하나).
스키마는 infra/sql(Postgres)와 개념적으로 동일해서 나중에 이전 쉬움.

테이블:
  canonical_field  표준 개념 사전 (canonical.py 시드)
  platform_field   플랫폼별 원천 필드 (추출 결과)
  field_mapping    platform_field → canonical 매핑 (제안/검수)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from admeta import canonical
from admeta.models import ExtractedField, MappingProposal

DEFAULT_DB = "data/admeta.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_field (
    key        TEXT PRIMARY KEY,
    kind       TEXT,
    data_type  TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS platform_field (
    platform    TEXT,
    api_name    TEXT,
    display_name TEXT,
    data_type   TEXT,
    category    TEXT,
    description TEXT,
    source_url  TEXT,
    PRIMARY KEY (platform, api_name)
);
CREATE TABLE IF NOT EXISTS field_mapping (
    platform      TEXT,
    api_name      TEXT,
    canonical_key TEXT,
    confidence    REAL,
    reasoning     TEXT,
    review_status TEXT,
    method        TEXT,
    reviewed_by   TEXT,          -- NULL=자동, 'human'=사람이 검수함(플라이휠 보존 대상)
    transform     TEXT,          -- 값 변환 규칙 (divide_by_million 등). NULL=그대로
    PRIMARY KEY (platform, api_name)
);
CREATE INDEX IF NOT EXISTS idx_mapping_canonical ON field_mapping(canonical_key);
"""


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    _migrate(con)
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """기존 DB 에 없는 컬럼 추가."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(field_mapping)")}
    for col in ("reviewed_by", "transform"):
        if col not in cols:
            con.execute(f"ALTER TABLE field_mapping ADD COLUMN {col} TEXT")
    con.commit()


def seed_canonical(con: sqlite3.Connection) -> int:
    rows = [(f.key, f.kind.value, f.data_type.value, f.description) for f in canonical.ALL_FIELDS]
    con.executemany(
        "INSERT OR REPLACE INTO canonical_field(key,kind,data_type,description) VALUES (?,?,?,?)",
        rows,
    )
    con.commit()
    return len(rows)


def upsert_field(con: sqlite3.Connection, platform: str, f: ExtractedField) -> None:
    con.execute(
        """INSERT OR REPLACE INTO platform_field
           (platform,api_name,display_name,data_type,category,description,source_url)
           VALUES (?,?,?,?,?,?,?)""",
        (platform, f.api_name, f.display_name, f.data_type, f.category, f.description, f.source_url),
    )


def is_human_reviewed(con: sqlite3.Connection, platform: str, api_name: str) -> bool:
    r = con.execute(
        "SELECT reviewed_by FROM field_mapping WHERE platform=? AND api_name=?",
        (platform, api_name),
    ).fetchone()
    return bool(r and r["reviewed_by"] == "human")


def upsert_mapping(
    con: sqlite3.Connection, platform: str, p: MappingProposal, method: str,
    reviewed_by: str | None = None,
) -> None:
    # 사람이 검수한 매핑은 자동 재실행(build)이 덮어쓰지 않는다 → 플라이휠 보존.
    if reviewed_by is None and is_human_reviewed(con, platform, p.api_name):
        return
    con.execute(
        """INSERT OR REPLACE INTO field_mapping
           (platform,api_name,canonical_key,confidence,reasoning,review_status,method,reviewed_by,transform)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (platform, p.api_name, p.canonical_key, p.confidence, p.reasoning,
         p.review_status, method, reviewed_by, p.transform),
    )


# --- 조회 ------------------------------------------------------------------
def cross_platform(con: sqlite3.Connection, platform: str, api_name: str) -> list[sqlite3.Row]:
    """'meta clicks = 구글 뭐?' — 같은 canonical 에 매핑된 타 플랫폼 필드들."""
    row = con.execute(
        "SELECT canonical_key FROM field_mapping WHERE platform=? AND api_name=?",
        (platform, api_name),
    ).fetchone()
    if not row or not row["canonical_key"]:
        return []
    # 거절된 매핑은 조회에서 제외 (사람 검수 결과가 실제로 반영되도록).
    return con.execute(
        """SELECT m.platform, m.api_name, m.confidence, m.review_status, f.description
           FROM field_mapping m JOIN platform_field f
             ON m.platform=f.platform AND m.api_name=f.api_name
           WHERE m.canonical_key=? AND m.review_status != 'rejected'
           ORDER BY m.platform""",
        (row["canonical_key"],),
    ).fetchall()


def search(con: sqlite3.Connection, q: str) -> list[dict]:
    """검색어(필드명/설명/캐노니컬키)와 매칭되는 개념을, 플랫폼별 대응 필드와 함께 반환.

    'clicks' 검색 → CLICKS 개념 + 각 플랫폼 필드(metrics.clicks / clicks ...).
    매칭 canonical 을 먼저 찾고, 그 개념의 (거절 제외) 전 플랫폼 필드를 묶어 준다.
    """
    like = f"%{q}%"
    # 언더바·공백·점 무시 정규화 ('campaign name'/'campaignname' → 'CAMPAIGN_NAME' 매칭)
    nlike = "%" + q.lower().replace("_", "").replace(" ", "").replace(".", "") + "%"

    # 관련도 점수: 이름 매칭(3) > 필드명 매칭(2) > 설명만 매칭(1).
    # 'clicks' → CLICKS(이름3)가 위, CPC/CTR(설명에 clicks 언급, 1)는 아래로.
    score: dict[str, int] = {}

    def bump(ck: str, s: int) -> None:
        if ck:
            score[ck] = max(score.get(ck, 0), s)

    # 3점: 캐노니컬 키 매칭
    for r in con.execute(
        """SELECT key FROM canonical_field
           WHERE key LIKE ? OR REPLACE(REPLACE(LOWER(key),'_',''),' ','') LIKE ?""",
        (like, nlike),
    ):
        bump(r["key"], 3)
    # 2점: 필드명(api_name) 매칭
    for r in con.execute(
        """SELECT DISTINCT m.canonical_key AS ck
           FROM field_mapping m
           WHERE m.canonical_key IS NOT NULL AND m.review_status != 'rejected'
             AND (m.api_name LIKE ? OR REPLACE(REPLACE(LOWER(m.api_name),'_',''),'.','') LIKE ?)""",
        (like, nlike),
    ):
        bump(r["ck"], 2)
    # 1점: 설명 매칭 (캐노니컬 한글 설명 + 필드 설명)
    for r in con.execute("SELECT key FROM canonical_field WHERE description LIKE ?", (like,)):
        bump(r["key"], 1)
    for r in con.execute(
        """SELECT DISTINCT m.canonical_key AS ck
           FROM field_mapping m JOIN platform_field f
             ON m.platform=f.platform AND m.api_name=f.api_name
           WHERE m.canonical_key IS NOT NULL AND m.review_status != 'rejected'
             AND f.description LIKE ?""",
        (like,),
    ):
        bump(r["ck"], 1)

    order = {"metric": 0, "dimension": 1, "derived": 2}
    out = []
    for ck, sc in score.items():
        cf = con.execute(
            "SELECT kind, description FROM canonical_field WHERE key=?", (ck,)
        ).fetchone()
        fields = con.execute(
            """SELECT m.platform, m.api_name, m.confidence, m.review_status,
                      m.reviewed_by, m.transform, f.description, f.data_type
               FROM field_mapping m JOIN platform_field f
                 ON m.platform=f.platform AND m.api_name=f.api_name
               WHERE m.canonical_key=? AND m.review_status != 'rejected'
               ORDER BY m.platform, m.confidence DESC""",
            (ck,),
        ).fetchall()
        if not fields:  # 개념은 매칭됐지만 아직 매핑된 필드가 없음(예: 리콜 갭)
            continue
        out.append({
            "canonical_key": ck,
            "kind": cf["kind"] if cf else "",
            "description": cf["description"] if cf else "",
            "_score": sc,
            "fields": [dict(r) for r in fields],
        })
    # 관련도 내림차순 → 종류(metric→dimension→derived) → 이름순
    out.sort(key=lambda g: (-g["_score"], order.get(g["kind"], 3), g["canonical_key"]))
    for g in out:
        g.pop("_score", None)
    return out


def search_unmapped(con: sqlite3.Connection, q: str, limit: int = 30) -> list[dict]:
    """아직 표준 개념에 매핑 안 된 원천 필드 중 검색어와 이름이 매칭되는 것.

    전체 필드의 90%+ 가 미매핑(니치 필드)이라 개념 검색만으론 안 보인다
    (예: bid_strategy_type). 이름 매칭만 쓰고 개수를 제한해 노이즈를 막는다.
    """
    like = f"%{q}%"
    nlike = "%" + q.lower().replace("_", "").replace(" ", "").replace(".", "") + "%"
    rows = con.execute(
        """SELECT f.platform, f.api_name, f.description, f.data_type
           FROM platform_field f LEFT JOIN field_mapping m
             ON f.platform=m.platform AND f.api_name=m.api_name
           WHERE (m.canonical_key IS NULL OR m.review_status='rejected')
             AND (f.api_name LIKE ? OR
                  REPLACE(REPLACE(REPLACE(LOWER(f.api_name),'_',''),'.',''),' ','') LIKE ?)
           ORDER BY LENGTH(f.api_name), f.platform
           LIMIT ?""",
        (like, nlike, limit),
    ).fetchall()
    return [dict(r) for r in rows]
