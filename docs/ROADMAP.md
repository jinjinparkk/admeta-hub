# Roadmap

## v1 — Meta + Google 파이프라인 완주 (현재 목표)

전체 흐름을 2개 플랫폼으로 끝까지 관통시킨다. "작동하는 서비스"가 v1의 정의.

- [ ] **M0. 프로젝트 뼈대** — 폴더 구조, README, Canonical 스키마 설계, DB DDL
- [ ] **M1. Canonical 사전 + 모델** — `canonical.py` 시드, Pydantic 모델(`models.py`)
- [ ] **M2. DB 셋업** — docker-compose(Postgres+pgvector), DDL, repository
- [ ] **M3. Crawler** — Meta / Google 광고 API 레퍼런스 문서 수집 → `data/raw/`
- [ ] **M4. LLM Extraction** — Claude tool use로 문서 → 필드 후보 JSON (재현 가능)
- [ ] **M5. Normalize** — 추출 필드 → Canonical 매핑 제안 (LLM + 룰 + confidence)
- [ ] **M6. Store + Embed** — DB 적재 + 설명 임베딩(pgvector)
- [ ] **M7. Search API** — FastAPI: 자연어(벡터) + 키워드(SQL) 하이브리드 검색
- [ ] **M8. Web UI** — Next.js: 검색창 + 결과 + 플랫폼 매핑 뷰
- [ ] **M9. 배포** — Docker, Cloud Run, 도메인 연결

## v1.1 — 플랫폼 확장
- [ ] TikTok, Kakao, Naver 크롤러 추가 (설정만 추가하면 되도록)

## v2 — 포트폴리오 심화
- [ ] **AI Agent** — "CTR 계산법?" → 메타 조회 + SQL 예시 생성 (tool use)
- [ ] **Spring Boot 게이트웨이** — 인증/캐싱/레이트리밋 (Java 어필)
- [ ] **Terraform + GitHub Actions** — IaC + CI/CD
- [ ] 매핑 검수(review) UI — LLM 제안을 사람이 승인/수정

## 지금 당장 다음 스텝
현재 **M0 완료 직전**. 다음은 **M1(Canonical 시드 + Pydantic 모델)** → **M2(DB DDL + docker-compose)**.
이 두 개까지 하면 "설계가 끝난 프로젝트"가 되고, 그 다음부터 크롤러로 실제 데이터가 흐르기 시작한다.
