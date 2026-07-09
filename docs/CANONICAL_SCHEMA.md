# Canonical Metadata Schema

이 문서가 이 프로젝트의 **핵심 IP**다. 플랫폼마다 다른 광고 API 필드를 하나의 표준 개념으로 묶는 사전(dictionary).

## 설계 원칙

1. **하나의 개념 = 하나의 Canonical Key.** (예: 클릭수는 무조건 `CLICKS`)
2. Canonical Key는 **플랫폼 중립적**이고 **대문자 SNAKE_CASE**.
3. 각 Canonical Key는 아래를 가진다:
   - `kind`: `metric`(측정값) | `dimension`(분류축) | `derived`(파생 지표)
   - `data_type`: `integer` | `decimal` | `currency` | `string` | `date` | `enum`
   - `unit`: 필요 시 (예: 통화, micros)
   - `description`: 자연어 설명 (임베딩 대상)
4. **매핑(mapping)** 은 Canonical → 플랫폼 방향으로 정의한다. 한 개념이 플랫폼별로 어떤 필드명·경로·변환을 갖는지.
5. **변환(transform)** 을 1급으로 취급한다. 이름만 다른 게 아니라 단위·구조가 다른 경우가 진짜 문제다.

---

## 정규화가 진짜 어려운 케이스 (= 포트폴리오 talking point)

단순히 `clicks` → `clicks` 같은 이름 매핑은 쉽다. 아래가 이 프로젝트의 진짜 가치다:

### 1. 단위 변환 — Google `cost_micros`
Google Ads는 비용을 **micros**(100만분의 1)로 준다.
```
Canonical SPEND (currency)
  ← Google:  metrics.cost_micros   → value / 1_000_000
  ← Meta:    spend                 → value (as-is)
```
`transform: divide_by_million` 을 메타데이터에 박아둔다.

### 2. 중첩 구조 — Meta `actions`
Meta는 전환수를 평면 필드가 아니라 `actions[]` 배열 안에 action_type 별로 준다.
```
Canonical CONVERSIONS (integer)
  ← Meta:   actions[?action_type=='offsite_conversion.fb_pixel_purchase'].value
  ← Google: metrics.conversions   (평면)
```
`extract_path: JMESPath` 를 메타데이터에 저장.

### 3. 이름 함정 — Meta `clicks` vs `inline_link_clicks`
Meta의 "클릭"은 전체 클릭(`clicks`)과 링크 클릭(`inline_link_clicks`)이 다르다.
Canonical `CLICKS` 는 전체 클릭으로 정의하고, 링크 클릭은 별도 `LINK_CLICKS` 로 분리한다.
→ **LLM 추출 시 이런 모호성을 사람이 검수(review)하는 워크플로우**가 있다는 것 자체가 엔지니어링 성숙도.

### 4. 파생 지표는 계산식으로 정의 — CTR, ROAS
플랫폼이 주기도 하지만, 정의가 다를 수 있어 **Canonical에서 계산식으로 표준화**한다.
```
CTR  = CLICKS / IMPRESSIONS
CPC  = SPEND / CLICKS
CPM  = SPEND / IMPRESSIONS * 1000
CVR  = CONVERSIONS / CLICKS
ROAS = REVENUE / SPEND
CPA  = SPEND / CONVERSIONS
```
AI Agent가 "CTR 계산하려면?" 물었을 때 이 정의 + 플랫폼별 원천 필드 + SQL 예시를 만들어 준다.

---

## Canonical 사전 (v1 초안)

### Metrics (측정값)

| Canonical Key | type | unit | Meta | Google |
|---|---|---|---|---|
| `IMPRESSIONS` | integer | — | `impressions` | `metrics.impressions` |
| `CLICKS` | integer | — | `clicks` | `metrics.clicks` |
| `LINK_CLICKS` | integer | — | `inline_link_clicks` | `metrics.clicks`* |
| `SPEND` | currency | account currency | `spend` | `metrics.cost_micros` ÷1e6 |
| `CONVERSIONS` | decimal | — | `actions[...]` (nested) | `metrics.conversions` |
| `REVENUE` | currency | account currency | `action_values[...]` | `metrics.conversions_value` |
| `REACH` | integer | — | `reach` | — (미지원) |
| `FREQUENCY` | decimal | — | `frequency` | — |
| `VIDEO_VIEWS` | integer | — | `video_play_actions[...]` | `metrics.video_views` |

\* Google에는 정확한 대응이 없어 근사 매핑 → 이런 "매핑 불완전성"도 메타데이터로 기록한다 (`confidence`, `note`).

### Dimensions (분류축)

| Canonical Key | type | Meta | Google |
|---|---|---|---|
| `DATE` | date | `date_start` | `segments.date` |
| `ACCOUNT_ID` | string | `account_id` | `customer.id` |
| `ACCOUNT_NAME` | string | `account_name` | `customer.descriptive_name` |
| `CAMPAIGN_ID` | string | `campaign_id` | `campaign.id` |
| `CAMPAIGN_NAME` | string | `campaign_name` | `campaign.name` |
| `AD_GROUP_ID` | string | `adset_id` | `ad_group.id` |
| `AD_GROUP_NAME` | string | `adset_name` | `ad_group.name` |
| `AD_ID` | string | `ad_id` | `ad_group_ad.ad.id` |
| `AD_NAME` | string | `ad_name` | `ad_group_ad.ad.name` |
| `DEVICE` | enum | `device_platform` | `segments.device` |
| `COUNTRY` | enum | `country` | `segments.geo_target_country` |
| `PLACEMENT` | enum | `publisher_platform`+`platform_position` | `segments.ad_network_type` |
| `OBJECTIVE` | enum | `objective` | `campaign.advertising_channel_type` |

### Derived (파생)

| Canonical Key | formula |
|---|---|
| `CTR` | `CLICKS / IMPRESSIONS` |
| `CPC` | `SPEND / CLICKS` |
| `CPM` | `SPEND / IMPRESSIONS * 1000` |
| `CVR` | `CONVERSIONS / CLICKS` |
| `ROAS` | `REVENUE / SPEND` |
| `CPA` | `SPEND / CONVERSIONS` |

> 이 표는 **사람이 직접 다 채우지 않는다.** LLM Extraction이 각 플랫폼 문서에서 후보를 뽑고 → 이 Canonical 사전에 매핑을 제안 → 사람이 검수. 위 표는 시드(seed)이자 정답지(ground truth) 역할.

---

## DB 표현

- `canonical_field` : Canonical Key 마스터 (kind, data_type, unit, description, formula)
- `platform_field` : 플랫폼 원천 필드 (platform, api_name, path, data_type, raw_description)
- `field_mapping` : canonical_field ↔ platform_field (transform, confidence, note, review_status)
- `platform_field.description_embedding` : 설명 임베딩 (pgvector) — 자연어 검색용

스키마 DDL: [`../infra/sql/001_init.sql`](../infra/sql/001_init.sql)
