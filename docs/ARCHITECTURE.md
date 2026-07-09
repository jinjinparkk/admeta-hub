# Architecture

## 데이터 흐름 (7단계)

```
① Document Crawler   각 플랫폼 광고 API 레퍼런스 문서 수집 (HTML/JSON)
        ↓
② Raw Document Store  원문을 backend/data/raw/{platform}/ 에 그대로 저장 (재현성)
        ↓
③ LLM Extraction     Claude로 문서에서 필드 후보 추출 → 구조화 JSON
                     (api_name, path, data_type, description)
        ↓
④ Normalize          추출된 플랫폼 필드를 Canonical 사전에 매핑 제안
                     (LLM 매핑 + 룰 기반 보정 + confidence)
        ↓
⑤ Store + Embed      PostgreSQL 저장 + 설명 임베딩(pgvector)
        ↓
⑥ Search API         자연어 검색(임베딩) + 정확 키워드 검색(SQL) 하이브리드
        ↓
⑦ Web UI (Next.js)   검색 / 매핑 뷰 / AI Agent
```

## 왜 이렇게 나눴나

- **크롤과 추출을 분리** → 문서 원문을 보관하므로 LLM 프롬프트를 바꿔가며 **재추출**이 가능(재현성/실험).
- **추출과 정규화를 분리** → 플랫폼 필드는 "있는 그대로", Canonical 매핑은 "해석"이라 layer가 다르다.
- **임베딩은 설명(description)에만** → 필드명이 아니라 "이 필드가 무슨 뜻인지"로 검색해야 자연어 검색이 유용.

## 모듈 구조 (backend)

```
backend/admeta/
├── config.py          설정 (env)
├── canonical.py       Canonical 사전 (seed) — 코드로 표현된 표준
├── models.py          Pydantic 모델 (LLM 추출 스키마, 매핑)
├── crawler/           ① 문서 수집
│   ├── base.py
│   ├── meta.py
│   └── google.py
├── extract/           ③ LLM 추출
│   └── llm_extractor.py
├── normalize/         ④ Canonical 매핑
│   └── mapper.py
├── db/                ⑤ 저장/임베딩
│   ├── schema.py
│   └── repository.py
└── api/               ⑥ FastAPI
    └── main.py
```

## v2 확장 지점

- **Spring Boot API 게이트웨이**: FastAPI 앞단에 두어 인증/레이트리밋/캐싱 담당. Java 역량 어필.
- **AI Agent**: LangGraph/자체 orchestration으로 "지표 계산법 질문 → 툴 콜(메타 조회 → SQL 생성)".
- **Cloud Run + Terraform + GitHub Actions**: IaC + CI/CD.

## 기술 선택 이유 (면접 대비)

| 선택 | 이유 |
|---|---|
| Claude (Anthropic) | 긴 API 문서 파싱 + 구조화 추출 정확도. tool use로 강제 JSON 스키마. |
| pgvector | 별도 벡터 DB 없이 Postgres 하나로 정형+벡터 → 운영 단순. |
| 설명만 임베딩 | 필드명 검색은 SQL이 낫고, 의미 검색만 벡터로 → 하이브리드. |
| FastAPI first | 파이프라인(Python)과 언어 통일, 가장 빠른 실동작. |
