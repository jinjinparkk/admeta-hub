"""Canonical metadata dictionary — the project's core IP.

플랫폼마다 다른 광고 API 필드를 하나의 표준 개념으로 묶는 시드(seed) 사전.
LLM Extraction이 각 플랫폼 문서에서 필드를 뽑으면, 이 사전에 매핑을 제안하고
사람이 검수한다. 여기 정의된 것이 정답지(ground truth) 역할을 한다.

설계 문서: docs/CANONICAL_SCHEMA.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(str, Enum):
    METRIC = "metric"        # 측정값 (impressions, clicks ...)
    DIMENSION = "dimension"  # 분류축 (date, campaign ...)
    DERIVED = "derived"      # 파생 지표 (ctr, roas ...)


class DataType(str, Enum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    CURRENCY = "currency"
    STRING = "string"
    DATE = "date"
    ENUM = "enum"


@dataclass(frozen=True)
class PlatformMapping:
    """하나의 Canonical 개념이 특정 플랫폼에서 어떻게 표현되는가."""

    platform: str            # "meta" | "google" | ...
    api_name: str            # 플랫폼 원천 필드명/경로
    transform: str | None = None   # "divide_by_million" 등 값 변환 규칙
    extract_path: str | None = None  # 중첩 구조 추출 경로 (JMESPath 등)
    confidence: float = 1.0  # 매핑 신뢰도 (근사 매핑이면 < 1.0)
    note: str | None = None


@dataclass(frozen=True)
class CanonicalField:
    """표준 개념 하나."""

    key: str                 # "CLICKS" (대문자 SNAKE_CASE)
    kind: Kind
    data_type: DataType
    description: str         # 자연어 설명 (임베딩 대상)
    unit: str | None = None
    formula: str | None = None  # derived 인 경우 계산식
    mappings: tuple[PlatformMapping, ...] = field(default_factory=tuple)


def _m(platform: str, api_name: str, **kw) -> PlatformMapping:
    return PlatformMapping(platform=platform, api_name=api_name, **kw)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
METRICS: list[CanonicalField] = [
    CanonicalField(
        "IMPRESSIONS", Kind.METRIC, DataType.INTEGER,
        "광고가 노출된 횟수.",
        mappings=(_m("meta", "impressions"), _m("google", "metrics.impressions")),
    ),
    CanonicalField(
        "CLICKS", Kind.METRIC, DataType.INTEGER,
        "광고에 발생한 전체 클릭 수 (링크 클릭 외 반응 포함).",
        mappings=(_m("meta", "clicks"), _m("google", "metrics.clicks")),
    ),
    CanonicalField(
        "LINK_CLICKS", Kind.METRIC, DataType.INTEGER,
        "랜딩 링크로 이동한 클릭 수. CLICKS 와 구분됨.",
        mappings=(
            _m("meta", "inline_link_clicks"),
            _m("google", "metrics.clicks", confidence=0.5,
               note="Google에는 링크클릭 전용 지표가 없어 근사 매핑"),
        ),
    ),
    CanonicalField(
        "SPEND", Kind.METRIC, DataType.CURRENCY,
        "집행 비용. 계정 통화 기준.", unit="account_currency",
        mappings=(
            _m("meta", "spend"),
            _m("google", "metrics.cost_micros", transform="divide_by_million",
               note="Google은 micros(1e-6) 단위 → 100만으로 나눠야 함"),
        ),
    ),
    CanonicalField(
        "CONVERSIONS", Kind.METRIC, DataType.DECIMAL,
        "전환 수 (구매·가입 등 목표 액션).",
        mappings=(
            _m("meta", "actions",
               extract_path="actions[?action_type=='offsite_conversion.fb_pixel_purchase'].value",
               note="Meta는 actions[] 배열에서 action_type별로 추출"),
            _m("google", "metrics.conversions"),
        ),
    ),
    CanonicalField(
        "REVENUE", Kind.METRIC, DataType.CURRENCY,
        "전환으로 발생한 매출액.", unit="account_currency",
        mappings=(
            _m("meta", "action_values",
               extract_path="action_values[?action_type=='offsite_conversion.fb_pixel_purchase'].value"),
            _m("google", "metrics.conversions_value"),
        ),
    ),
    CanonicalField(
        "REACH", Kind.METRIC, DataType.INTEGER,
        "광고를 본 순 사용자 수 (중복 제외).",
        mappings=(_m("meta", "reach"),),  # Google 미지원
    ),
    CanonicalField(
        "FREQUENCY", Kind.METRIC, DataType.DECIMAL,
        "1인당 평균 노출 횟수 = IMPRESSIONS / REACH.",
        mappings=(_m("meta", "frequency"),),
    ),
    CanonicalField(
        "VIDEO_VIEWS", Kind.METRIC, DataType.INTEGER,
        "동영상 조회 수.",
        mappings=(
            _m("meta", "video_play_actions",
               extract_path="video_play_actions[?action_type=='video_view'].value"),
            _m("google", "metrics.video_views"),
        ),
    ),
]

# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------
DIMENSIONS: list[CanonicalField] = [
    CanonicalField("DATE", Kind.DIMENSION, DataType.DATE, "집계 기준 날짜.",
                   mappings=(_m("meta", "date_start"), _m("google", "segments.date"))),
    CanonicalField("ACCOUNT_ID", Kind.DIMENSION, DataType.STRING, "광고 계정 ID.",
                   mappings=(_m("meta", "account_id"), _m("google", "customer.id"))),
    CanonicalField("ACCOUNT_NAME", Kind.DIMENSION, DataType.STRING, "광고 계정 이름.",
                   mappings=(_m("meta", "account_name"), _m("google", "customer.descriptive_name"))),
    CanonicalField("CAMPAIGN_ID", Kind.DIMENSION, DataType.STRING, "캠페인 ID.",
                   mappings=(_m("meta", "campaign_id"), _m("google", "campaign.id"))),
    CanonicalField("CAMPAIGN_NAME", Kind.DIMENSION, DataType.STRING, "캠페인 이름.",
                   mappings=(_m("meta", "campaign_name"), _m("google", "campaign.name"))),
    CanonicalField("AD_GROUP_ID", Kind.DIMENSION, DataType.STRING,
                   "광고 그룹 ID. Meta는 adset, Google은 ad_group.",
                   mappings=(_m("meta", "adset_id"), _m("google", "ad_group.id"))),
    CanonicalField("AD_GROUP_NAME", Kind.DIMENSION, DataType.STRING, "광고 그룹 이름.",
                   mappings=(_m("meta", "adset_name"), _m("google", "ad_group.name"))),
    CanonicalField("AD_ID", Kind.DIMENSION, DataType.STRING, "개별 광고(소재) ID.",
                   mappings=(_m("meta", "ad_id"), _m("google", "ad_group_ad.ad.id"))),
    CanonicalField("AD_NAME", Kind.DIMENSION, DataType.STRING, "개별 광고 이름.",
                   mappings=(_m("meta", "ad_name"), _m("google", "ad_group_ad.ad.name"))),
    CanonicalField("DEVICE", Kind.DIMENSION, DataType.ENUM, "노출 디바이스 (mobile/desktop 등).",
                   mappings=(_m("meta", "device_platform"), _m("google", "segments.device"))),
    CanonicalField("COUNTRY", Kind.DIMENSION, DataType.ENUM, "노출 국가.",
                   mappings=(_m("meta", "country"), _m("google", "segments.geo_target_country"))),
    CanonicalField("PLACEMENT", Kind.DIMENSION, DataType.ENUM, "노출 지면/배치.",
                   mappings=(_m("meta", "publisher_platform"),
                             _m("google", "segments.ad_network_type"))),
    CanonicalField("OBJECTIVE", Kind.DIMENSION, DataType.ENUM, "캠페인 목표/유형.",
                   mappings=(_m("meta", "objective"),
                             _m("google", "campaign.advertising_channel_type"))),
    CanonicalField("BID_STRATEGY", Kind.DIMENSION, DataType.ENUM,
                   "입찰 전략 유형 (수동 CPC / 타겟 CPA / 최대 전환 등).",
                   mappings=(_m("google", "campaign.bidding_strategy_type"),
                             _m("dv360", "FILTER_BID_STRATEGY_TYPE_NAME"),
                             _m("cm360", "paidSearchBidStrategy"),
                             _m("pinterest", "ad_group_bid_type"),
                             _m("tiktok", "bid_type"))),
]

# --------------------------------------------------------------------------
# Derived — 계산식으로 표준화 (플랫폼이 주는 값 대신 정의를 통일)
# --------------------------------------------------------------------------
DERIVED: list[CanonicalField] = [
    CanonicalField("CTR", Kind.DERIVED, DataType.DECIMAL, "클릭률.", formula="CLICKS / IMPRESSIONS"),
    CanonicalField("CPC", Kind.DERIVED, DataType.CURRENCY, "클릭당 비용.", formula="SPEND / CLICKS"),
    CanonicalField("CPM", Kind.DERIVED, DataType.CURRENCY, "1000회 노출당 비용.", formula="SPEND / IMPRESSIONS * 1000"),
    CanonicalField("CVR", Kind.DERIVED, DataType.DECIMAL, "전환율.", formula="CONVERSIONS / CLICKS"),
    CanonicalField("ROAS", Kind.DERIVED, DataType.DECIMAL, "광고비 대비 매출.", formula="REVENUE / SPEND"),
    CanonicalField("CPA", Kind.DERIVED, DataType.CURRENCY, "전환당 비용.", formula="SPEND / CONVERSIONS"),
]

ALL_FIELDS: list[CanonicalField] = [*METRICS, *DIMENSIONS, *DERIVED]

# key 로 빠르게 조회
BY_KEY: dict[str, CanonicalField] = {f.key: f for f in ALL_FIELDS}


def get(key: str) -> CanonicalField:
    """Canonical key 로 필드 조회. 없으면 KeyError."""
    return BY_KEY[key.upper()]


def platform_keys() -> set[str]:
    """사전에 등장하는 모든 플랫폼 이름."""
    return {mp.platform for f in ALL_FIELDS for mp in f.mappings}
