"""Google Ads API 필드 레퍼런스 크롤러.

Google는 필드 문서를 서버 렌더링(정적 HTML)으로 제공 → httpx 로 바로 수집 가능.
metrics(측정값) / segments(분류축) + 주요 리소스(campaign, ad_group ...) 페이지를 긁는다.
"""
from __future__ import annotations

import re

from .base import Crawler, Source

API_VERSION = "v24"
_BASE = f"https://developers.google.com/google-ads/api/fields/{API_VERSION}"

# 핵심 정의 페이지만. metrics=측정값(Canonical METRICS), segments=분류축(Canonical DIMENSIONS).
# 리소스별 속성 페이지(campaign/ad_group…)는 필드 수백 개라 v1 범위에선 제외.
# 각 metric 문서에 "Resources with metrics" 섹션이 있어 어떤 리소스에 붙는지도 원문에 포함됨.
SOURCES: list[Source] = [
    Source("metrics", f"{_BASE}/metrics"),
    Source("segments", f"{_BASE}/segments"),
]

# 각 필드는 <h2 id="metrics.clicks"> 형태로 문서에 박혀 있음
_FIELD_RE = re.compile(r'<h2[^>]*id="([a-z][a-z0-9_.]+)"', re.I)


class GoogleCrawler(Crawler):
    platform = "google"


def preview_fields(html: str, limit: int = 8) -> tuple[int, list[str]]:
    """원문 HTML에서 필드 id 를 훑어 개수/샘플만 반환 (로깅용, 파싱 아님)."""
    ids = _FIELD_RE.findall(html)
    seen: list[str] = []
    for x in ids:
        if x not in seen:
            seen.append(x)
    return len(seen), seen[:limit]


def run() -> None:
    print("Crawling Google Ads API field reference...")
    with GoogleCrawler() as c:
        records = c.crawl(SOURCES)
        print("\n필드 미리보기 (원문에서 감지된 필드 수 / 샘플):")
        for rec in records:
            html = (c.out_dir / f"{rec.slug}.html").read_text(encoding="utf-8")
            n, sample = preview_fields(html)
            print(f"  {rec.slug:12s} 필드 {n:>4d}개  예: {', '.join(sample[:5])}")


if __name__ == "__main__":
    run()
