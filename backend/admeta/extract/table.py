"""범용 표 파서 — "이름 | 설명" 표에서 필드 추출.

MS Learn(Bing/LinkedIn), Pinterest, CM360, DV360 등이 필드명·설명을 표로 준다.
헤더를 부분 매칭해 이름열/설명열을 찾는다. 설명 전용 열이 없으면(CM360/DV360:
API Name | Report Builder Name | Type) 사람이 읽는 이름(Report Builder Name)을
설명 대용으로 쓴다.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from admeta.models import ExtractedField

# 이름열 헤더 키워드(부분 매칭). 'name' 단독은 제외(Report Builder Name 오인 방지).
_NAME_KW = ("api", "field", "metric", "filter", "value", "column",
            "breakdown", "dimension", "attribute", "property", "key")
_DESC_KW = ("description", "definition", "meaning", "details")
_DESC_FALLBACK_KW = ("report builder", "display", "name")  # 설명열 없을 때 대용


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _find_col(header: list[str], keywords) -> int | None:
    for i, h in enumerate(header):
        if any(kw in h for kw in keywords):
            return i
    return None


def parse(html: str, source_url: str | None = None) -> list[ExtractedField]:
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen: set[str] = set()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header = [_clean(c.get_text()).lower() for c in rows[0].find_all(["th", "td"])]
        if not header or not any(header):
            continue  # 헤더 없는 표(X 등)는 스킵
        name_i = _find_col(header, _NAME_KW)
        if name_i is None:
            continue
        desc_i = _find_col(header, _DESC_KW)
        if desc_i is None:  # 설명 전용 열 없음 → 대용(Report Builder Name 등)
            desc_i = next((i for i, h in enumerate(header)
                           if i != name_i and any(kw in h for kw in _DESC_FALLBACK_KW)), None)
        if desc_i is None or desc_i == name_i:
            continue

        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(name_i, desc_i):
                continue
            name = _clean(cells[name_i].get_text())
            desc = _clean(cells[desc_i].get_text())
            if not name or len(name) > 80 or name in seen:
                continue
            seen.add(name)
            fields.append(ExtractedField(
                api_name=name, display_name=name, description=desc,
                category="unknown", source_url=source_url,
            ))
    return fields
