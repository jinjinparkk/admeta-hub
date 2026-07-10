"""X (Twitter) Ads 전용 파서 — 헤더가 표 안쪽에 있는 표 처리.

docs.x.com/x-ads-api/analytics 는 표 첫 <tr> 이 빈 셀이고 진짜 헤더가 그 다음
행에 들어있다(범용 table.py 는 row0 만 헤더로 봐서 전부 스킵). 그래서 표마다
헤더 행을 스캔해서 찾는다. 세 종류를 뽑는다:

  1. 메트릭 표    header = Metric | Description | ... | Data Type   → category=metric
  2. 세그먼트 표  header = Segmentation Type | ...                → category=dimension(설명 없음)

파생 메트릭 표(Derived Metric | Exposed Metric Calculation)는 스킵 — API 필드가
아니라 계산식이고(CPM/CTR 등), 파생 개념은 canonical 에 이미 derived 로 있다.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from admeta.models import ExtractedField

_NAME_KW = ("metric", "segmentation type")     # 이름열 헤더 키워드
_DESC_KW = ("description", "calculation")       # 설명열 헤더 키워드
_TYPE_KW = ("data type",)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _find_col(header: list[str], keywords) -> int | None:
    for i, h in enumerate(header):
        if any(kw in h for kw in keywords):
            return i
    return None


def _header_row(rows) -> tuple[int, list[str]] | None:
    """이름열+설명열을 가진 첫 행을 헤더로 판정. (index, 소문자 헤더) 반환."""
    for ri, r in enumerate(rows):
        cells = [_clean(c.get_text()).lower() for c in r.find_all(["th", "td"])]
        if not any(cells):
            continue
        if any("derived" in c for c in cells):      # 파생 메트릭 표 → 스킵
            return None
        if _find_col(cells, _NAME_KW) is not None and _find_col(cells, _DESC_KW) is not None:
            return ri, cells
    return None


def parse(html: str, source_url: str | None = None) -> list[ExtractedField]:
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen: set[str] = set()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        found = _header_row(rows)
        if found is None:
            continue
        hdr_i, header = found
        name_i = _find_col(header, _NAME_KW)
        desc_i = _find_col(header, _DESC_KW)
        type_i = _find_col(header, _TYPE_KW)
        # 세그먼트 표(Segmentation Type)는 dimension, 그 외는 metric
        is_dim = "segmentation type" in header[name_i]

        for tr in rows[hdr_i + 1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(name_i, desc_i):
                continue
            name = _clean(cells[name_i].get_text())
            desc = _clean(cells[desc_i].get_text())
            if not name or len(name) > 80 or name in seen:
                continue
            seen.add(name)
            data_type = (
                _clean(cells[type_i].get_text())
                if type_i is not None and len(cells) > type_i
                else None
            )
            fields.append(ExtractedField(
                api_name=name,
                display_name=name,
                data_type=data_type or None,
                description=desc,
                category="dimension" if is_dim else "metric",
                source_url=source_url,
            ))
    return fields
