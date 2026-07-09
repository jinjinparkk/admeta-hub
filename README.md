# admeta-hub

**AI 기반 광고 플랫폼 메타데이터 표준화 플랫폼**
_AI-powered Ad Metadata Standardization Platform_

> 광고 플랫폼(Meta, Google, TikTok, Kakao …)마다 제각각인 API 메타데이터를 AI가 자동으로 분석·추출하고, 하나의 **표준 스키마(Canonical Schema)** 로 정규화하여, **자연어 검색**과 **플랫폼 간 필드 매핑**을 제공하는 웹 서비스.

---

## 이게 왜 "RAG 챗봇"과 다른가

대부분의 LLM 포트폴리오:

```
PDF → Vector DB → RAG → 챗봇     (누구나 만든다)
```

admeta-hub:

```
문서 → AI Extraction → 표준 Metadata 생성 → 검색/매핑 서비스
```

**LLM을 "검색"이 아니라 "데이터 정규화(normalization)"에 사용한다.** 이게 핵심이다.
RAG는 긴 설명·원문 문서를 *보강*하는 보조 용도로만 쓴다.

### 실제로 푸는 문제

광고 데이터 마트를 만들 때 진짜 겪는 고통:

| 개념(Canonical) | Meta | Google | TikTok | Naver |
|---|---|---|---|---|
| `CLICKS` | `clicks` | `metrics.clicks` | `click` | `clk_cnt` |
| `SPEND` | `spend` | `metrics.cost_micros` (÷1,000,000) | `spend` | `sales_amt` |
| `AD_GROUP` | `adset_id` | `ad_group.id` | `adgroup_id` | `grp_no` |

같은 "클릭수"인데 플랫폼마다 이름·타입·단위·중첩 구조가 전부 다르다.
이걸 사람이 매핑 문서 만들어서 관리하는 게 지금의 현실 → **AI가 자동으로 하게 한다.**

---

## Architecture

```
                광고 API 문서
     Meta   Google   TikTok   Kakao
       │       │        │        │
       └───────┴────────┴────────┘
                   │
          ① Document Crawler          문서 수집
                   │
          ② Raw Document Store        원문 보관 (data/raw)
                   │
          ③ LLM Metadata Extraction   필드명·타입·설명 → 표준 JSON
                   │
          ④ Canonical Metadata DB     정규화 저장 (PostgreSQL)
                   │
          ⑤ Embedding (설명만)         pgvector
                   │
          ⑥ AI Search API             자연어 + 정확 키워드 검색
                   │
          ⑦ Next.js Web UI            누구나 검색 가능한 인터페이스
```

자세한 내용: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 핵심 차별점 (포트폴리오 강조점)

1. **LLM = 데이터 정규화 엔진** — 검색이 아니라 표준 메타데이터 생성에 사용
2. **Canonical Metadata 설계** — 플랫폼별 필드를 하나의 개념으로 묶는 표준 사전 → [`docs/CANONICAL_SCHEMA.md`](docs/CANONICAL_SCHEMA.md)
3. **AI Agent** — "CTR 계산하려면?" → 메타데이터 조회 + 설명 조회 + SQL 예시 생성까지 자동
4. **실서비스 웹** — GitHub 링크가 아니라 `https://admeta-hub.com` 에서 직접 검색해볼 수 있는 임팩트

---

## 기술 스택

| 레이어 | v1 (현재) | v2 (확장) |
|---|---|---|
| Web | Next.js | — |
| API | FastAPI (Python) | + Spring Boot 게이트웨이 (Java) |
| Pipeline | Python (crawler / LLM extract / normalize) | — |
| DB | PostgreSQL + pgvector | — |
| LLM | Claude (Anthropic) | — |
| Infra | Docker, docker-compose | Cloud Run, Terraform, GitHub Actions |

---

## 로드맵

v1 목표: **Meta + Google 2개 플랫폼으로 전체 파이프라인 완주** (크롤 → 추출 → 정규화 → 검색).
상세: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## 개발 시작

```bash
# 로컬 DB (Postgres + pgvector)
cd infra && docker compose up -d

# 백엔드
cd backend
pip install -e ".[dev]"
cp .env.example .env      # ANTHROPIC_API_KEY 등 입력
pytest
```
