"""주간 파이프라인 — crawl → extract → build(map+DB) 전 과정을 한 번에.

Windows 작업 스케줄러가 주 1회 이걸 실행한다. 한 플랫폼이 실패해도
나머지는 계속 가도록 단계별로 예외를 격리한다.

실행: py -3 -m admeta.pipeline
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from admeta.crawler.engine import crawl_platform
from admeta.extract.engine import PARSERS, extract_platform
from admeta.normalize import build
from admeta.platforms import active_platforms


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run() -> int:
    _log("=== admeta 주간 파이프라인 시작 ===")
    failures = 0

    for spec in active_platforms():
        # 1) 크롤 (원문 갱신)
        try:
            _log(f"crawl: {spec.key}")
            crawl_platform(spec.key)
        except Exception:
            failures += 1
            _log(f"!! crawl 실패 {spec.key}\n{traceback.format_exc()}")
            continue
        # 2) 추출 (원문 → 구조화)
        if spec.key in PARSERS:
            try:
                _log(f"extract: {spec.key}")
                extract_platform(spec.key)
            except Exception:
                failures += 1
                _log(f"!! extract 실패 {spec.key}\n{traceback.format_exc()}")

    # 3) 매핑 + DB 적재 (전 플랫폼 한 번에)
    try:
        _log("build: 매핑 + DB 적재")
        build.main()
    except Exception:
        failures += 1
        _log(f"!! build 실패\n{traceback.format_exc()}")

    # 3.5) 오토시드 — 새 플랫폼 핵심 지표 필드명 매칭으로 확정(감사 앞에서 보호).
    try:
        _log("autoseed: 새 플랫폼 핵심 지표 시딩")
        from admeta.normalize import autoseed
        autoseed.main()
    except Exception:
        failures += 1
        _log(f"!! autoseed 실패\n{traceback.format_exc()}")

    # 4) AI 정리 (정답지 시딩 + LLM 감사) — 매주 깨끗한 상태 재생성. 사람검수는 보존.
    try:
        _log("cleanup: 시딩 + AI 감사")
        from admeta.normalize import cleanup
        cleanup.main()
    except Exception:
        failures += 1
        _log(f"!! cleanup 실패\n{traceback.format_exc()}")

    _log(f"=== 파이프라인 종료 (실패 {failures}건) ===")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
