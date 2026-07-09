"""Pydantic 모델 — LLM 추출 결과와 매핑 제안의 스키마.

이 스키마가 곧 LLM에게 강제하는 출력 형식(tool use)이자 DB 적재 형식이다.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """LLM이 플랫폼 API 문서에서 뽑아낸 원천 필드 하나 (③ Extraction 결과)."""

    api_name: str = Field(..., description="플랫폼 문서에 적힌 필드명/경로 (예: metrics.cost_micros)")
    display_name: Optional[str] = Field(None, description="문서상의 사람이 읽는 이름")
    data_type: Optional[str] = Field(None, description="문서상의 타입 (int64, string 등)")
    category: Optional[Literal["metric", "dimension", "segment", "resource", "unknown"]] = "unknown"
    description: str = Field("", description="필드 설명 원문 — 임베딩 대상")
    unit: Optional[str] = Field(None, description="단위 힌트 (micros, currency 등)")
    source_url: Optional[str] = Field(None, description="추출 근거 문서 URL")


class ExtractionResult(BaseModel):
    """한 플랫폼 문서 하나에 대한 추출 결과 묶음."""

    platform: str
    source_url: str
    fields: list[ExtractedField] = Field(default_factory=list)


class MappingProposal(BaseModel):
    """추출 필드 → Canonical 매핑 제안 (④ Normalize 결과, 사람 검수 전)."""

    platform: str
    api_name: str
    canonical_key: Optional[str] = Field(
        None, description="매핑되는 Canonical 개념. 매핑 대상 없으면 None"
    )
    transform: Optional[str] = Field(None, description="값 변환 규칙 (divide_by_million 등)")
    extract_path: Optional[str] = Field(None, description="중첩 추출 경로")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    reasoning: str = Field("", description="왜 이렇게 매핑했는지 (LLM 근거)")
    review_status: Literal["proposed", "approved", "rejected", "edited"] = "proposed"
