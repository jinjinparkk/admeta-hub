"""플랫폼 레지스트리 — "크롤러 N개"가 아니라 "엔진 1개 + 설정 N개".

새 플랫폼 추가 = 여기에 PlatformSpec 한 덩어리 추가. 크롤 엔진(crawler/engine.py)은
이 레지스트리만 읽고 fetch 방식(static/browser/manual)을 골라 원문을 저장한다.

fetch:
  static  — 서버 렌더링 HTML. httpx 로 바로 수집 (구글 계열·MS 계열·Pinterest·X).
  browser — JS 렌더링 SPA. 헤드리스 브라우저 렌더링 필요 (Meta·TikTok·Amazon).
  manual  — 1st-party 공개 문서 없음. 수동 시드 (The Trade Desk).
parse:
  parser  — 구조 반듯 → 결정적 파서.
  llm     — 비정형 → LLM 추출.
  manual  — 손으로 입력.

정찰 근거: 2026-07-07 문서 정찰 결과 (memory/admeta_hub.md 참조).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """크롤 대상 문서 하나. slug = 저장 파일명.

    parser — 플랫폼 기본 파서와 다른 파서를 쓰는 소스면 파서 키 지정
    (예: pinterest 는 1st-party glossary=table + supermetrics 미러=supermetrics).
    """

    slug: str
    url: str
    parser: str = ""


@dataclass(frozen=True)
class PlatformSpec:
    """플랫폼 한 개의 크롤 설정."""

    key: str                       # 내부 식별자 (= data/raw/{key}/ 폴더명)
    name: str                      # 표시 이름
    fetch: str                     # "static" | "browser" | "manual"
    parse: str                     # "parser" | "llm" | "manual"
    sources: tuple[Source, ...]    # 크롤할 문서들
    active: bool = False           # Wave 0 활성 여부
    notes: str = ""


# --- Google 계열 -------------------------------------------------------------
_GOOGLE_ADS = "https://developers.google.com/google-ads/api/fields/v24"
_SA360 = "https://developers.google.com/search-ads/reporting/api/reference/fields/v0"

# --- 레지스트리 (12 커넥터; Instagram 은 Meta 에 흡수) ------------------------
PLATFORMS: dict[str, PlatformSpec] = {
    "google_ads": PlatformSpec(
        key="google_ads",
        name="Google Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source("metrics", f"{_GOOGLE_ADS}/metrics"),
            Source("segments", f"{_GOOGLE_ADS}/segments"),
            # 리소스 페이지 — campaign.name, ad_group.id, customer.descriptive_name 등 속성(dimension)
            Source("campaign", f"{_GOOGLE_ADS}/campaign"),
            Source("ad_group", f"{_GOOGLE_ADS}/ad_group"),
            Source("ad_group_ad", f"{_GOOGLE_ADS}/ad_group_ad"),
            Source("customer", f"{_GOOGLE_ADS}/customer"),
        ),
        active=True,
        notes="필드=<h2 id='metrics.xxx'>+테이블. 구조 반듯 → 결정적 파서. 리소스 페이지 4종 포함.",
    ),
    "meta": PlatformSpec(
        key="meta",
        name="Meta (Facebook + Instagram Ads)",
        fetch="browser",
        parse="llm",
        sources=(
            # 메트릭(clicks/impressions/spend...) — Graph API 레퍼런스 노드
            Source(
                "metrics",
                "https://developers.facebook.com/documentation/ads-commerce/"
                "marketing-api/reference/ad-account/insights",
            ),
            # 분류축(age/gender/device...) — breakdowns
            Source(
                "breakdowns",
                "https://developers.facebook.com/documentation/ads-commerce/"
                "marketing-api/insights/breakdowns",
            ),
        ),
        active=True,
        notes="SPA. Instagram 광고 지표는 동일(publisher_platform=instagram 분류축).",
    ),
    # --- Wave 1: static 팬아웃 ------------------------------------------------
    "sa360": PlatformSpec(
        key="sa360",
        name="Search Ads 360",
        fetch="static",
        parse="parser",
        sources=(
            Source("metrics", f"{_SA360}/metrics"),
            Source("segments", f"{_SA360}/segments"),
            Source("overview", f"{_SA360}/overview"),
        ),
        active=True,
        notes="Google Ads 와 필드 구조 동일 → google_ads 파서 재활용.",
    ),
    "dv360": PlatformSpec(
        key="dv360",
        name="Display & Video 360",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "filters-metrics",
                "https://developers.google.com/bid-manager/reference/rest/v2/filters-metrics",
            ),
        ),
        active=True,
        notes="Bid Manager API v2. 메트릭+분류축 한 페이지. 표 큼.",
    ),
    "cm360": PlatformSpec(
        key="cm360",
        name="Campaign Manager 360",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "dimensions",
                "https://developers.google.com/doubleclick-advertisers/v5/dimensions",
            ),
        ),
        active=True,
        notes="v5. 분류축+메트릭 통합 페이지.",
    ),
    "bing": PlatformSpec(
        key="bing",
        name="Microsoft Advertising (Bing Ads)",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "ad-performance",
                "https://learn.microsoft.com/en-us/advertising/reporting-service/"
                "adperformancereportcolumn?view=bingads-13",
            ),
            # 리포트 종류별 컬럼 페이지가 ~10개. Wave 1 에서 나머지 확장.
        ),
        active=True,
        notes="리포트 종류별 페이지 분산. 설명에 deprecated 메타데이터 포함.",
    ),
    "linkedin": PlatformSpec(
        key="linkedin",
        name="LinkedIn Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "schema",
                "https://learn.microsoft.com/en-us/linkedin/marketing/integrations/"
                "ads-reporting/ads-reporting-schema?view=li-lms-2026-04",
            ),
        ),
        active=True,
        notes="overview 아닌 schema 페이지에 설명 있음. viral* 중복 주의.",
    ),
    "pinterest": PlatformSpec(
        key="pinterest",
        name="Pinterest Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "metrics-glossary",
                "https://developers.pinterest.com/docs/analytics-and-reports/metrics-glossary/",
            ),
            Source(
                "ads-reporting",
                "https://developers.pinterest.com/docs/analytics-and-reports/ads-reporting/",
            ),
            # 1st-party glossary 는 UI 지표 21개뿐(spend/conversions 없음) →
            # API 필드 전체는 supermetrics 미러로 보강 (delivery_metrics API 는 토큰 필요)
            Source(
                "supermetrics-fields",
                "https://docs.supermetrics.com/docs/pinterest-ads-fields",
                parser="supermetrics",
            ),
        ),
        active=True,
        notes="display_name(UI) vs API enum 2계층. delivery_metrics/get 로 JSON 정의도 가능.",
    ),
    "x": PlatformSpec(
        key="x",
        name="X (Twitter) Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source("analytics", "https://docs.x.com/x-ads-api/analytics"),
        ),
        active=True,
        notes="developer.x.com 은 402. docs.x.com 써야 함. 표 헤더가 안쪽 행 → x.py 전용 파서.",
    ),
    # --- Wave 2: 1st-party 가 SPA/비공개 → supermetrics 미러(static) ----------
    # 필드명은 플랫폼 API 원 이름 그대로 미러링됨 → 매핑 용도 충분.
    "tiktok": PlatformSpec(
        key="tiktok",
        name="TikTok Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "supermetrics-fields",
                "https://docs.supermetrics.com/docs/tiktok-ads-fields",
                parser="supermetrics",
            ),
        ),
        active=True,
        notes="1st-party(business-api.tiktok.com/portal/docs)는 SPA → 미러 사용. "
              "fallback=GitHub tiktok/tiktok-business-api-sdk OpenAPI.",
    ),
    "amazon": PlatformSpec(
        key="amazon",
        name="Amazon Ads",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "supermetrics-fields",
                "https://docs.supermetrics.com/docs/amazon-ads-fields",
                parser="supermetrics",
            ),
        ),
        active=True,
        notes="1st-party(advertising.amazon.com/API/docs)는 SPA → 미러 사용. "
              "fallback=GitHub amzn/ads-advanced-tools-docs.",
    ),
    "ttd": PlatformSpec(
        key="ttd",
        name="The Trade Desk",
        fetch="static",
        parse="parser",
        sources=(
            Source(
                "supermetrics-fields",
                "https://docs.supermetrics.com/docs/the-trade-desk-fields",
                parser="supermetrics",
            ),
        ),
        active=True,
        notes="1st-party 공개문서 없음(파트너 로그인 SPA) → 미러 사용.",
    ),
}


def active_platforms() -> list[PlatformSpec]:
    return [p for p in PLATFORMS.values() if p.active]


def get_platform(key: str) -> PlatformSpec:
    if key not in PLATFORMS:
        raise KeyError(f"unknown platform '{key}'. known: {', '.join(PLATFORMS)}")
    return PLATFORMS[key]
