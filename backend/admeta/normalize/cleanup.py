"""AI 정리 패스 — 검증된 시드 + LLM 감사로 매핑을 싹 정리.

1) seed: canonical.py 의 검증된 매핑(정답지)을 authoritative 로 박는다.
   → 핵심 개념(SPEND, CLICKS...)에 정답 필드가 반드시 존재 (리콜 갭 원천 차단).
2) audit: 시드도 사람검수도 아닌 자동매핑을 LLM 이 엄격 판정.
   core=개념의 정확한 대표 / related=관련되나 별개(대조군·예측치·벤치마크·오가닉) / different=딴 개념.
   core 만 남기고 related/different 는 거절(사유 기록).

사람이 이미 내린 검수(reviewed_by='human')와 시드는 건드리지 않는다.
실행: py -3 -m admeta.normalize.cleanup
"""
from __future__ import annotations

from admeta import canonical
from admeta.db import store
from admeta.normalize.mapper import make_client

_ALIAS = {"google": "google_ads", "meta": "meta"}

_AUDIT_TOOL = {
    "name": "judge",
    "description": "플랫폼 필드가 표준 개념을 진짜로 나타내는지 판정.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["core", "related", "different"],
                "description": "core=이 개념의 정확한 대표 필드. "
                               "related=관련되나 별개 하위개념(실험 대조군/예측치/벤치마크/오가닉/세그먼트). "
                               "different=전혀 다른 개념.",
            },
            "reason": {"type": "string", "description": "한 문장 근거"},
        },
        "required": ["verdict", "reason"],
    },
}


def seed_authoritative(con) -> int:
    """canonical.py 의 검증 매핑을 approved/seed 로 적재.

    한 필드가 여러 canonical 에 매핑될 수 있으나(예: metrics.clicks 는 CLICKS 1.0 /
    LINK_CLICKS 0.5) DB 는 필드당 한 개념만 저장 → 신뢰도 높은 쪽을 채택.
    사람이 이미 검수한 필드는 건드리지 않는다.
    """
    best: dict[tuple[str, str], tuple[float, str]] = {}
    for cf in canonical.ALL_FIELDS:
        for mp in cf.mappings:
            plat = _ALIAS.get(mp.platform, mp.platform)
            key = (plat, mp.api_name)
            if key not in best or mp.confidence > best[key][0]:
                best[key] = (mp.confidence, cf.key)

    n = 0
    for (plat, api), (conf, ck) in best.items():
        if not con.execute(
            "SELECT 1 FROM platform_field WHERE platform=? AND api_name=?", (plat, api)
        ).fetchone():
            continue  # 아직 안 크롤한 필드(리소스 페이지 등)는 스킵
        if store.is_human_reviewed(con, plat, api):
            continue  # 사람 판단 존중
        con.execute(
            """INSERT OR REPLACE INTO field_mapping
               (platform,api_name,canonical_key,confidence,reasoning,
                review_status,method,reviewed_by)
               VALUES (?,?,?,?,'canonical.py 검증 매핑','approved','seed','seed')""",
            (plat, api, ck, conf),
        )
        n += 1
    con.commit()
    return n


def audit(con, client, model) -> tuple[int, int]:
    """시드/사람 아닌 자동매핑을 LLM 으로 엄격 감사. core 만 유지, 나머지 거절."""
    rows = con.execute(
        """SELECT m.canonical_key AS ck, m.platform AS p, m.api_name AS a, f.description AS d
           FROM field_mapping m JOIN platform_field f
             ON m.platform=f.platform AND m.api_name=f.api_name
           WHERE m.canonical_key IS NOT NULL AND m.review_status != 'rejected'
             AND m.method != 'seed' AND m.reviewed_by IS NULL"""
    ).fetchall()
    kept = rej = 0
    for r in rows:
        cf = canonical.BY_KEY[r["ck"]]
        prompt = (
            f"표준 개념: {r['ck']} — {cf.description}\n\n"
            f"플랫폼 필드: {r['a']}\n"
            f"필드 설명: {r['d'] or '(문서에 설명 없음 — 필드 이름으로 판단)'}\n\n"
            f"이 필드가 위 표준 개념의 정확한 대표인가요?"
        )
        resp = client.messages.create(
            model=model, max_tokens=200, temperature=0,
            tools=[_AUDIT_TOOL], tool_choice={"type": "tool", "name": "judge"},
            messages=[{"role": "user", "content": prompt}],
        )
        v = next(b.input for b in resp.content if b.type == "tool_use")
        verdict = v.get("verdict", "related")
        reason = str(v.get("reason", ""))[:120]
        if verdict == "core":
            kept += 1
        else:
            con.execute(
                """UPDATE field_mapping SET review_status='rejected',
                   reviewed_by='ai_audit', reasoning=? WHERE platform=? AND api_name=?""",
                (f"{verdict}: {reason}", r["p"], r["a"]),
            )
            rej += 1
        print(f"  [{r['ck']:13s}] {r['p']:11s} {r['a']:34s} -> {verdict}")
    con.commit()
    return kept, rej


def main() -> int:
    con = store.connect()
    print("1) 정답지 시딩...")
    print(f"   시드 매핑 {seed_authoritative(con)}건 적재\n")
    client, model = make_client()
    print(f"2) AI 감사 (LLM={model})...")
    kept, rej = audit(con, client, model)
    print(f"\n감사 완료: core 유지 {kept} / 거절 {rej}\n")

    print("=== 정리 후 검수 현황 ===")
    for r in con.execute(
        "SELECT review_status,COUNT(*) n FROM field_mapping "
        "WHERE canonical_key IS NOT NULL GROUP BY review_status"
    ):
        print(f"   {r['review_status']:10s} {r['n']}")
    print("\n=== 핵심 개념 점검 ===")
    for api, plat in [("spend", "meta"), ("clicks", "meta"), ("cpc", "meta"),
                      ("impressions", "meta"), ("cpm", "meta")]:
        rows = store.cross_platform(con, plat, api)
        got = ", ".join(f"{x['platform'].replace('google_ads','G').replace('meta','M')}:{x['api_name']}"
                        for x in rows)
        print(f"   {api:12s} -> {got or '(없음)'}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
