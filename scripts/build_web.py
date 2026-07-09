# -*- coding: utf-8 -*-
"""정적 배포용 웹페이지 생성 — DB → web/index.html.

주간 파이프라인 뒤 실행하면 최신 매핑으로 정적 사이트가 갱신된다.
web/_template.html(자리표시자 __DATA__) 에 데이터를 심어 완성 HTML 을 만든다.
GitHub Pages / Netlify / Vercel / GCS 정적 호스팅에 그대로 올리면 됨.

실행: py -3 scripts/build_web.py   (repo 루트에서)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from admeta.db import store  # noqa: E402


def _clean_dt(dt: str | None) -> str:
    if not dt:
        return ""
    dt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", dt)  # [x](url) -> x
    return re.sub(r"\s+", " ", dt).strip()[:40]


def _load_data(con) -> list[dict]:
    keys = [r["key"] for r in con.execute(
        "SELECT DISTINCT canonical_key key FROM field_mapping "
        "WHERE canonical_key IS NOT NULL AND review_status!='rejected'")]
    order = {"metric": 0, "dimension": 1, "derived": 2}
    data = []
    for ck in sorted(k for k in keys if k):
        for grp in store.search(con, ck):
            if grp["canonical_key"] != ck:
                continue
            data.append({
                "canonical_key": grp["canonical_key"], "kind": grp["kind"],
                "description": grp["description"],
                "fields": [{
                    "platform": f["platform"], "api_name": f["api_name"],
                    "confidence": f["confidence"], "review_status": f["review_status"],
                    "reviewed_by": f["reviewed_by"],
                    "description": (f["description"] or "")[:180],
                    "data_type": _clean_dt(f["data_type"]),
                } for f in grp["fields"]],
            })
            break
    data.sort(key=lambda x: (order.get(x["kind"], 3), x["canonical_key"]))
    return data


def main() -> int:
    con = store.connect(ROOT / "backend" / "data" / "admeta.db")
    data = _load_data(con)
    con.close()

    template = (ROOT / "web" / "_template.html").read_text(encoding="utf-8")
    html = template.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = ROOT / "web" / "index.html"
    out.write_text(html, encoding="utf-8")

    plats = {f["platform"] for g in data for f in g["fields"]}
    print(f"생성: {out}  ({len(html):,} bytes, {len(data)}개념 "
          f"{sum(len(g['fields']) for g in data)}필드 {len(plats)}플랫폼)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
