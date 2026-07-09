"""추출 엔진 — data/raw/{key}/ 원문 → 구조화 필드(JSON).

크롤 엔진과 짝. 레지스트리 parse 방식(parser/llm)에 맞는 파서를 골라
ExtractedField 리스트로 만들고 data/parsed/{key}.json 에 저장한다.

SA360 은 Google Ads 와 문서 구조가 같아 google.parse 를 재활용한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from admeta.extract import google, meta, table
from admeta.models import ExtractedField
from admeta.platforms import get_platform

# 플랫폼 → 파서 함수 (parse 방식이 'parser'/'llm' 이어도 실제 결정적 파서로 처리)
PARSERS = {
    "google_ads": google.parse,
    "sa360": google.parse,     # 구글 devsite 동일 구조 재활용
    "meta": meta.parse,
    # 표(name|description) 기반 문서 — 범용 표 파서 공용
    "bing": table.parse,
    "linkedin": table.parse,
    "pinterest": table.parse,
    "cm360": table.parse,
    "dv360": table.parse,
}


def extract_platform(
    key: str, raw_dir: str | Path = "data/raw", out_dir: str | Path = "data/parsed"
) -> list[ExtractedField]:
    spec = get_platform(key)
    parser = PARSERS.get(key)
    if parser is None:
        raise NotImplementedError(f"'{key}' 파서 미구현 (parse={spec.parse})")

    manifest_path = Path(raw_dir) / key / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"원문 없음: {manifest_path} — 먼저 크롤하세요")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    fields: list[ExtractedField] = []
    seen: set[str] = set()
    for rec in manifest:
        html = Path(rec["path"]).read_text(encoding="utf-8")
        for f in parser(html, rec["url"]):
            if f.api_name in seen:      # 페이지 간 중복 제거
                continue
            seen.add(f.api_name)
            fields.append(f)
        print(f"  [{key}] {rec['slug']:14s} -> 누적 {len(fields)} fields")

    out_path = Path(out_dir) / f"{key}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([f.model_dump() for f in fields], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [{key}] 저장: {out_path} ({len(fields)} fields)")
    return fields
