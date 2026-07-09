"""크롤 엔진 — 레지스트리 하나로 모든 플랫폼을 크롤한다.

플랫폼별 크롤러를 따로 두지 않는다. platforms.PLATFORMS 의 fetch 방식(static/browser)
을 보고 fetchers.FETCHERS 에서 함수를 골라 원문을 data/raw/{key}/ 에 저장하고
manifest.json 을 남긴다. 파싱은 하지 않는다 (extract 단계의 몫).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from admeta.crawler.base import CrawlRecord, _slugify
from admeta.crawler.fetchers import FETCHERS
from admeta.platforms import PlatformSpec, get_platform


def crawl_platform(key: str, raw_dir: str | Path = "data/raw") -> list[CrawlRecord]:
    """레지스트리의 한 플랫폼을 크롤해 원문 저장. manual/미지원 fetch 는 스킵."""
    spec: PlatformSpec = get_platform(key)

    if spec.fetch == "manual":
        print(f"  [{spec.key}] manual 플랫폼 — 크롤 스킵 ({spec.notes})")
        return []

    fetch = FETCHERS.get(spec.fetch)
    if fetch is None:
        raise ValueError(f"'{spec.key}': 알 수 없는 fetch 방식 '{spec.fetch}'")

    out_dir = Path(raw_dir) / spec.key
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[CrawlRecord] = []
    for src in spec.sources:
        text, status = fetch(src.url)
        path = out_dir / f"{_slugify(src.slug)}.html"
        path.write_text(text, encoding="utf-8")
        rec = CrawlRecord(
            slug=src.slug,
            url=src.url,
            path=str(path),
            status=status,
            bytes=len(text.encode("utf-8")),
        )
        records.append(rec)
        print(
            f"  [{spec.key}] {src.slug:14s} {rec.status} "
            f"{rec.bytes:>10,d} bytes -> {path.name}"
        )

    _write_manifest(out_dir, records)
    return records


def _write_manifest(out_dir: Path, records: list[CrawlRecord]) -> None:
    (out_dir / "manifest.json").write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
