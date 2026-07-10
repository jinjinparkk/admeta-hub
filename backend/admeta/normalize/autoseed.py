"""이름 기반 오토시드 — 새 플랫폼의 핵심 지표를 필드명 매칭으로 확정 매핑.

새 플랫폼(SA360/DV360/CM360/Bing/LinkedIn/Pinterest)은 canonical.py seed 가 없어
임베딩+LLM 에만 의존 → 커버리지 구멍. 하지만 clicks/impressions/cost 같은 핵심은
필드명이 뻔하다. 정규화된 필드명(또는 마지막 세그먼트)이 개념 토큰과 정확히 일치하면
authoritative(reviewed_by='human') 로 박는다 → 감사/재빌드에도 보존.

실행: py -3 -m admeta.normalize.autoseed
pipeline 에서 build 뒤 cleanup 앞에 실행(멱등).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from admeta.db import store

# 개념 → 필드명 토큰(정규화: 소문자·영숫자만). 정확 일치만 채택(오탐 최소화).
TOKENS: dict[str, list[str]] = {
    "CLICKS": ["clicks", "pinclicks"],
    "IMPRESSIONS": ["impressions"],
    "SPEND": ["spend", "cost", "costmicros", "costinlocalcurrency", "spendinmicrodollar", "totalspend",
              "billedchargelocalmicro",   # X: micro 단위 과금액
              "advertisercostusd",        # TTD
              "mediacostadvertiser",      # DV360: METRIC_MEDIA_COST_ADVERTISER
              "mediacost"],               # CM360: mediaCost
    "CPC": ["cpc", "averagecpc", "avgcpc", "costperclick"],
    "CPM": ["cpm", "averagecpm", "avgcpm"],
    "CTR": ["ctr", "averagectr", "clickthroughrate", "ctrrate"],
    "CONVERSIONS": ["conversions", "totalconversions",
                    "attributedconversions14d"],  # Amazon: 14일 어트리뷰션 창(리포트 표준)
    "REACH": ["reach", "cumulativereach",         # Amazon
              "uniquereachimpressionreach"],      # DV360: METRIC_UNIQUE_REACH_IMPRESSION_REACH
    "FREQUENCY": ["frequency", "averagefrequency"],
    "REVENUE": ["revenue", "revenuemicros", "conversionsvalue", "conversionvalue"],
    "VIDEO_VIEWS": ["videoviews", "videototalviews",
                    "videoplayactions"],          # TikTok
    "LINK_CLICKS": ["outboundclicks", "urlclicks"],
    "CVR": ["cvr", "conversionrate"],             # TikTok/Amazon/Pinterest
    "ROAS": ["roas", "conversionsvaluepercost"],  # Amazon 'roas' / Google conversions_value_per_cost
    "CAMPAIGN_ID": ["campaignid"],
    "CAMPAIGN_NAME": ["campaignname"],
    "AD_GROUP_ID": ["adgroupid", "adsetid"],
    "AD_GROUP_NAME": ["adgroupname", "adsetname"],
    "AD_ID": ["adid"],
    "AD_NAME": ["adname"],
    "ACCOUNT_ID": ["accountid", "customerid"],
    "ACCOUNT_NAME": ["accountname"],
    "DEVICE": ["device", "devicetype"],
    "COUNTRY": ["country"],
    "DATE": ["date"],
}
# 토큰 → 개념 역인덱스
_TOK2KEY = {tok: key for key, toks in TOKENS.items() for tok in toks}

# micro 단위 필드 → ÷1e6 변환 필요 (정규화 이름 기준)
_MICRO_TOKENS = {"costmicros", "revenuemicros", "billedchargelocalmicro",
                 "spendinmicrodollar"}

# canonical.py 시드가 있는 google_ads/meta 도 포함 — 시드에 빠진 이름 정확일치
# 매핑(meta ctr, google conversions_value_per_cost 등)을 여기서 메운다.
NEW_PLATFORMS = ["google_ads", "meta",
                 "sa360", "dv360", "cm360", "bing", "linkedin", "pinterest",
                 "x", "tiktok", "amazon", "ttd"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# 리소스/타입 접두어 (이것만 떼고 나머지 전체가 토큰과 일치해야 함).
# 언더바로 끝단어만 자르면 average_cost→cost 오인 → 접두어 제거 방식 사용.
_PREFIXES = ("metrics.", "segments.", "metric_", "filter_", "segment_")


def _match_key(api_name: str) -> str | None:
    """필드명 전체(예: campaign.name) 또는 접두어 제거 후(예: FILTER_COUNTRY→country)
    가 토큰과 '정확히' 일치할 때만 개념 반환. 부분 일치는 오탐이라 안 씀."""
    full = _norm(api_name)              # campaign.name -> campaignname
    if full in _TOK2KEY:
        return _TOK2KEY[full]
    low = api_name.lower()
    for pre in _PREFIXES:
        if low.startswith(pre):
            return _TOK2KEY.get(_norm(api_name[len(pre):]))  # cost_micros->costmicros
    return None


def seed_platform(con, platform: str, parsed_dir="data/parsed") -> list[tuple[str, str]]:
    p = Path(parsed_dir) / f"{platform}.json"
    if not p.exists():
        return []
    fields = json.loads(p.read_text(encoding="utf-8"))
    # 개념별 후보 중 가장 짧은(가장 정확한) 필드명 선택
    best: dict[str, str] = {}
    for f in fields:
        key = _match_key(f["api_name"])
        if not key:
            continue
        if key not in best or len(f["api_name"]) < len(best[key]):
            best[key] = f["api_name"]
    applied = []
    for key, api in best.items():
        # micro 단위 필드는 ÷1e6 변환 기록 (cost_micros, billed_charge_local_micro 등)
        stripped = api
        for pre in _PREFIXES:
            if api.lower().startswith(pre):
                stripped = api[len(pre):]
                break
        transform = "divide_by_million" if _norm(stripped) in _MICRO_TOKENS else None
        con.execute(
            """INSERT OR REPLACE INTO field_mapping
               (platform,api_name,canonical_key,confidence,reasoning,review_status,method,reviewed_by,transform)
               VALUES (?,?,?,1.0,'오토시드: 필드명 정확일치','approved','autoseed','human',?)""",
            (platform, api, key, transform),
        )
        applied.append((key, api))
    con.commit()
    return applied


def main() -> int:
    con = store.connect()
    # 이전 오토시드 제거(재실행 멱등 — 오탐 잔재 청소)
    con.execute("DELETE FROM field_mapping WHERE method='autoseed'")
    con.commit()
    for plat in NEW_PLATFORMS:
        applied = seed_platform(con, plat)
        print(f"[{plat}] {len(applied)}개 시드: " +
              ", ".join(f"{k}={a}" for k, a in sorted(applied)))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
