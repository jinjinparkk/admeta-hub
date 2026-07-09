"""크롤러 공통 베이스 (① Document Crawler).

역할은 딱 하나: 문서 원문을 그대로 가져와 data/raw/{platform}/ 에 저장한다.
구조 파싱/해석은 여기서 하지 않는다 (그건 ③ LLM Extraction의 몫).
원문을 보관하므로 프롬프트를 바꿔가며 재추출이 가능하다(재현성).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

_UA = "Mozilla/5.0 (admeta-hub crawler; +https://admeta-hub.com)"


@dataclass(frozen=True)
class Source:
    """크롤 대상 문서 하나."""

    slug: str   # 저장 파일명 (예: "metrics")
    url: str


@dataclass
class CrawlRecord:
    """크롤 결과 한 건 (manifest 용)."""

    slug: str
    url: str
    path: str
    status: int
    bytes: int


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-")


class Crawler:
    """플랫폼별 크롤러의 베이스."""

    platform: str = "base"

    def __init__(self, raw_dir: str | Path = "data/raw", timeout: float = 30.0):
        self.out_dir = Path(raw_dir) / self.platform
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            headers={"User-Agent": _UA},
            timeout=timeout,
            follow_redirects=True,
        )

    # -- 개별 문서 -------------------------------------------------------
    def fetch(self, url: str) -> httpx.Response:
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp

    def save_raw(self, slug: str, content: str, ext: str = "html") -> Path:
        path = self.out_dir / f"{_slugify(slug)}.{ext}"
        path.write_text(content, encoding="utf-8")
        return path

    # -- 배치 -----------------------------------------------------------
    def crawl(self, sources: list[Source]) -> list[CrawlRecord]:
        records: list[CrawlRecord] = []
        for src in sources:
            resp = self.fetch(src.url)
            path = self.save_raw(src.slug, resp.text)
            rec = CrawlRecord(
                slug=src.slug,
                url=src.url,
                path=str(path),
                status=resp.status_code,
                bytes=len(resp.content),
            )
            records.append(rec)
            print(f"  [{self.platform}] {src.slug:12s} {rec.status} "
                  f"{rec.bytes:>9,d} bytes -> {path.name}")
        self._write_manifest(records)
        return records

    def _write_manifest(self, records: list[CrawlRecord]) -> None:
        manifest = self.out_dir / "manifest.json"
        manifest.write_text(
            json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
