"""Google 계열 필드 파서 (결정적, bs4).

Google Ads / SA360 필드 레퍼런스는 필드마다
    <h2 id="metrics.clicks">metrics.clicks</h2>
    + 상세 테이블(행: Field description / Category / Data Type / ...)
구조라 파싱이 100% 결정적이다. LLM 불필요 (memory: "AI는 비정형에만").

SA360 도 동일 구조라 이 파서를 그대로 재활용한다.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from admeta.models import ExtractedField

# Google Category 원문 → ExtractedField.category 리터럴
_CATEGORY = {
    "METRIC": "metric",
    "SEGMENT": "segment",
    "ATTRIBUTE": "dimension",
    "RESOURCE": "resource",
}


def _clean(text: str) -> str:
    """줄바꿈·중복 공백 정리."""
    return re.sub(r"\s+", " ", text).strip()


def parse(html: str, source_url: str | None = None) -> list[ExtractedField]:
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []

    for h2 in soup.find_all("h2", id=True):
        api_name = h2.get("id")
        if "." not in api_name:  # 필드는 metrics.xxx / segments.xxx 형태
            continue
        table = h2.find_parent("table")
        if table is None:
            continue

        kv: dict[str, str] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) >= 2:
                kv[_clean(cells[0].get_text())] = _clean(cells[1].get_text())

        if "Category" not in kv:  # 상세 테이블이 아닌 h2 (페이지 제목 등) 걸러냄
            continue

        fields.append(
            ExtractedField(
                api_name=api_name,
                display_name=api_name.split(".")[-1],
                data_type=kv.get("Data Type") or None,
                category=_CATEGORY.get(kv.get("Category", ""), "unknown"),
                description=kv.get("Field description", ""),
                source_url=source_url,
            )
        )
    return fields
