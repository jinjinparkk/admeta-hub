"""사람 검수 CLI — 매핑 제안을 승인/거절해 field_mapping.review_status 를 갱신.

검수 결과가 곧 학습 데이터(정답/오답 라벨)가 되어 매퍼 개선의 연료가 된다 = 플라이휠.
같은 canonical 에 여러 필드가 붙은 그룹부터 보여준다(노이즈일 확률 높음).

실행:
    py -3 -m admeta.review --stats          검수 현황 요약 (비대화형)
    py -3 -m admeta.review --list           매핑 그룹 전체 보기 (비대화형)
    py -3 -m admeta.review --list --noisy    한 canonical·플랫폼에 2개+ 붙은 것만
    py -3 -m admeta.review                    대화형 검수 (그룹 단위, a/r/s/q)
    py -3 -m admeta.review CLICKS             특정 canonical 만 검수
"""
from __future__ import annotations

import sys
from collections import defaultdict

from admeta.db import store


def _groups(con):
    rows = con.execute(
        """SELECT m.canonical_key AS ck, m.platform AS p, m.api_name AS a,
                  m.confidence AS c, m.review_status AS rs, f.description AS d
           FROM field_mapping m JOIN platform_field f
             ON m.platform=f.platform AND m.api_name=f.api_name
           WHERE m.canonical_key IS NOT NULL
           ORDER BY m.canonical_key, m.platform, m.confidence DESC"""
    ).fetchall()
    g = defaultdict(list)
    for r in rows:
        g[r["ck"]].append(r)
    return g


def _is_noisy(rows) -> bool:
    """한 플랫폼에서 같은 canonical 로 2개 이상 매핑되면 노이즈 의심."""
    per_plat = defaultdict(int)
    for r in rows:
        per_plat[r["p"]] += 1
    return any(v > 1 for v in per_plat.values())


def cmd_stats(con) -> None:
    print("검수 현황 (review_status):")
    for r in con.execute(
        "SELECT review_status, COUNT(*) n FROM field_mapping "
        "WHERE canonical_key IS NOT NULL GROUP BY review_status"
    ):
        print(f"  {r['review_status']:10s} {r['n']}")
    human = con.execute(
        "SELECT COUNT(*) n FROM field_mapping WHERE reviewed_by='human'"
    ).fetchone()["n"]
    print(f"  (그중 사람 검수: {human}개 — 주간 재실행에도 보존됨)")
    g = _groups(con)
    noisy = [k for k, rows in g.items() if _is_noisy(rows)]
    print(f"\n매핑된 canonical: {len(g)}개 / 노이즈 의심 그룹: {len(noisy)}개")
    if noisy:
        print("  노이즈 의심:", ", ".join(noisy))


def cmd_list(con, noisy_only: bool) -> None:
    for ck, rows in _groups(con).items():
        if noisy_only and not _is_noisy(rows):
            continue
        flag = "  ⚠노이즈" if _is_noisy(rows) else ""
        print(f"\n[{ck}]{flag}")
        for r in rows:
            print(f"   {r['rs']:9s} {r['c']:.2f} {r['p']:11s} {r['a']:36s} {r['d'][:45]}")


def _set_status(con, platform, api, status) -> None:
    # reviewed_by='human' 표시 → 주간 build 가 이 행을 덮어쓰지 않음(플라이휠 보존).
    con.execute(
        "UPDATE field_mapping SET review_status=?, reviewed_by='human' "
        "WHERE platform=? AND api_name=?",
        (status, platform, api),
    )
    con.commit()


def cmd_review(con, only_key: str | None) -> None:
    groups = _groups(con)
    keys = [only_key.upper()] if only_key else [k for k, r in groups.items() if _is_noisy(r)]
    if not keys:
        print("검수할 그룹이 없습니다.")
        return
    print("각 항목: [a]승인 [r]거절 [s]건너뜀 [q]종료\n")
    for ck in keys:
        rows = groups.get(ck, [])
        print(f"\n=== [{ck}] {len(rows)}개 매핑 ===")
        for r in rows:
            print(f"  {r['p']} · {r['a']}\n    설명: {r['d'][:80]}\n    현재 {r['rs']} (conf {r['c']:.2f})")
            ans = input("    > ").strip().lower()
            if ans == "q":
                print("종료."); return
            if ans == "a":
                _set_status(con, r["p"], r["a"], "approved"); print("    ✓ 승인")
            elif ans == "r":
                _set_status(con, r["p"], r["a"], "rejected"); print("    ✗ 거절")
            else:
                print("    - 건너뜀")


def main(argv: list[str]) -> int:
    con = store.connect()
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    if argv and argv[0] == "--stats":
        cmd_stats(con); return 0
    if argv and argv[0] == "--list":
        cmd_list(con, noisy_only="--noisy" in argv); return 0
    only = argv[0] if argv and not argv[0].startswith("-") else None
    cmd_review(con, only)
    cmd_stats(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
