"""Fetch 방식별 플러그인 — URL → (본문, HTTP status).

static  : httpx 정적 수집 (서버 렌더링 HTML).
browser : 헤드리스 브라우저 렌더링 (JS SPA). 주 1회 자동 실행이 목표라 Playwright 사용.

원문을 그대로 반환할 뿐, 파싱/해석은 하지 않는다 (그건 extract 단계의 몫).
"""
from __future__ import annotations

import httpx

_UA = "Mozilla/5.0 (admeta-hub crawler; +https://admeta-hub.com)"


def fetch_static(url: str, timeout: float = 30.0) -> tuple[str, int]:
    """서버 렌더링 페이지를 httpx 로 수집."""
    with httpx.Client(
        headers={"User-Agent": _UA}, timeout=timeout, follow_redirects=True
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text, resp.status_code


def fetch_browser(url: str, timeout: float = 60.0) -> tuple[str, int]:
    """JS 렌더링 SPA 를 헤드리스 브라우저로 렌더링 후 완성된 HTML 반환.

    Playwright 미설치 시 설치 안내와 함께 명확히 실패한다.
        pip install playwright && python -m playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise RuntimeError(
            "browser fetch 에는 Playwright 가 필요합니다:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=_UA)
            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = page.content()
        finally:
            browser.close()
    return html, 200


FETCHERS = {
    "static": fetch_static,
    "browser": fetch_browser,
}
