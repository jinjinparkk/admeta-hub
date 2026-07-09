"""매핑 빌드 파이프라인 — 전체 필드를 캐노니컬에 매핑하고 SQLite 에 적재.

비용 최적화: 값싼 임베딩으로 먼저 거르고(GATE), 그럴듯한 후보(top-sim>=GATE)만
비싼 LLM verify 를 호출한다. 대부분의 니치 필드는 캐노니컬에 대응 개념이 없으므로
LLM 을 부르지 않고 unmapped 로 둔다.

실행: py -3 -m admeta.normalize.build
"""
from __future__ import annotations

import json
from pathlib import Path

from admeta.db import store
from admeta.models import ExtractedField, MappingProposal
from admeta.normalize.mapper import EmbeddingRecall, llm_verify, make_client
from admeta.platforms import active_platforms

GATE = 0.50  # 임베딩 top-sim 이 이 미만이면 LLM 안 부르고 unmapped


def _load_parsed(key: str, parsed_dir="data/parsed") -> list[ExtractedField]:
    p = Path(parsed_dir) / f"{key}.json"
    return [ExtractedField(**d) for d in json.loads(p.read_text(encoding="utf-8"))]


def main() -> int:
    con = store.connect()
    print(f"canonical 시드: {store.seed_canonical(con)}개")
    recall = EmbeddingRecall()
    client, model = make_client()
    print(f"임베딩 게이트 GATE={GATE}, LLM={model}\n")

    for spec in active_platforms():
        fields = _load_parsed(spec.key)
        gated = mapped = 0
        for f in fields:
            store.upsert_field(con, spec.key, f)
            cands = recall.candidates(f, k=8)
            if cands[0][1] < GATE:  # 게이트 아웃 → LLM 안 부름
                store.upsert_mapping(
                    con, spec.key,
                    MappingProposal(platform=spec.key, api_name=f.api_name,
                                    canonical_key=None, confidence=cands[0][1],
                                    reasoning="임베딩 유사도 낮음 — 대응 캐노니컬 없음(추정)",
                                    review_status="proposed"),
                    method="embedding-gate",
                )
                continue
            gated += 1
            prop = llm_verify(f, cands, client, model)
            store.upsert_mapping(con, spec.key, prop, method="embedding+llm")
            if prop.canonical_key:
                mapped += 1
        con.commit()
        print(f"[{spec.key}] 필드 {len(fields)} / LLM호출 {gated} / 매핑성공 {mapped}")

    # 데모: 'meta X = 구글 뭐?'
    print("\n=== 크로스플랫폼 조회 데모 ===")
    for api in ("clicks", "impressions", "spend", "cpc"):
        rows = store.cross_platform(con, "meta", api)
        others = [f"{r['platform']}:{r['api_name']}" for r in rows if r["platform"] != "meta"]
        print(f"  meta.{api:12s} -> {', '.join(others) if others else '(매핑된 타 플랫폼 없음)'}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
