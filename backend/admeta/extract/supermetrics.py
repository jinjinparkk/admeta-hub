"""Supermetrics 필드 문서 파서 — third-party 미러.

1st-party 공개 문서가 없거나(TTD) SPA 라 정적 크롤이 안 되는(TikTok/Amazon)
플랫폼은 docs.supermetrics.com/docs/{platform}-fields 미러를 쓴다. 필드명은
플랫폼 API 원 이름을 그대로 미러링하므로 매핑 용도로 충분하다.

DOM 이 클래스 기반으로 반듯하다: 필드 하나 = <table class="field-table">,
안에 td.field-name(API명) / td.field-label(사람 라벨) / td.field-description(설명)
+ "Field type"(dimension|metric) / "Data type" 메타 행.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from admeta.models import ExtractedField


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse(html: str, source_url: str | None = None) -> list[ExtractedField]:
    soup = BeautifulSoup(html, "html.parser")
    fields: list[ExtractedField] = []
    seen: set[str] = set()

    for ft in soup.find_all("table", class_="field-table"):
        name_td = ft.find("td", class_="field-name")
        if name_td is None:
            continue
        # 링크 아이콘 등 부속 요소 제거 후 텍스트만
        for a in name_td.find_all("a"):
            a.decompose()
        name = _clean(name_td.get_text())
        if not name or len(name) > 80 or name in seen:
            continue

        label_td = ft.find("td", class_="field-label")
        desc_td = ft.find("td", class_="field-description")

        # "Field type" / "Data type" 메타 행 (라벨 셀 옆 값 셀)
        field_type = data_type = None
        for meta_td in ft.find_all("td", class_="field-meta-label"):
            key = _clean(meta_td.get_text()).lower()
            val_td = meta_td.find_next_sibling("td")
            if val_td is None:
                continue
            val = _clean(val_td.get_text())
            if key == "field type":
                field_type = val.lower()
            elif key == "data type":
                data_type = val

        category = "metric" if field_type == "metric" else (
            "dimension" if field_type == "dimension" else "unknown"
        )
        seen.add(name)
        fields.append(ExtractedField(
            api_name=name,
            display_name=_clean(label_td.get_text()) if label_td else name,
            data_type=data_type,
            description=_clean(desc_td.get_text()) if desc_td else "",
            category=category,
            source_url=source_url,
        ))
    return fields
