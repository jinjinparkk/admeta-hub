"""Meta 필드 파서 (결정적).

Meta 문서(개발자 documentation)는 SPA 지만, Playwright 로 렌더링하면 본문이
마크다운 표로 잡힌다:
    | `clicks`<br><br>*numeric string* | The number of clicks on your ads. |
즉 비정형이 아니라 규칙적 → LLM 불필요, 정규식 파서로 충분.

- 메트릭 페이지(ad-account/insights): '#### Fields' ~ '#### Error Codes' 구간만이
  실제 반환 필드. 그 앞뒤 '#### Parameters' 는 쿼리 파라미터라 제외.
- breakdowns 페이지: 표 전체가 분류축(dimension).
"""
from __future__ import annotations

import html
import re

from admeta.models import ExtractedField

# | `name`<br><br>*type* | description |
_ROW = re.compile(r"\|\s*`([^`]+)`((?:<br>)*\s*\*[^*]+\*)?\s*\|\s*(.*?)\s*\|")


def _unescape(raw: str) -> str:
    # Playwright content() 가 이중 이스케이프(&amp;lt;) → 두 번 해제
    return html.unescape(html.unescape(raw))


def _clean_desc(text: str) -> str:
    text = text.replace("<br>", " ")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [텍스트](url) → 텍스트
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _clean_type(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<br>|\*", "", text)).strip() or None


def _rows_in(segment: str, category: str, source_url: str | None) -> list[ExtractedField]:
    out: list[ExtractedField] = []
    seen: set[str] = set()
    for m in _ROW.finditer(segment):
        name = m.group(1).strip()
        desc = _clean_desc(m.group(3))
        if name in seen or not desc or desc.lower() == "description":
            continue
        seen.add(name)
        out.append(
            ExtractedField(
                api_name=name,
                display_name=name,
                data_type=_clean_type(m.group(2)),
                category=category,
                description=desc,
                source_url=source_url,
            )
        )
    return out


def parse(raw_html: str, source_url: str | None = None) -> list[ExtractedField]:
    text = _unescape(raw_html)

    # 메트릭 페이지: Fields 섹션만 잘라서 파싱
    m = re.search(r"####\s*Fields\b", text)
    if m:
        start = m.end()
        end_m = re.search(r"####\s*(Error Codes|Parameters)\b", text[start:])
        end = start + end_m.start() if end_m else len(text)
        return _rows_in(text[start:end], "metric", source_url)

    # breakdowns 페이지: 표 전체가 분류축
    return _rows_in(text, "dimension", source_url)
