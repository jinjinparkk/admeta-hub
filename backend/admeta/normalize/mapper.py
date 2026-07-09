"""필드 → Canonical 매핑 (2단계: 임베딩 리콜 + LLM 검증).

1) EmbeddingRecall — 필드 설명을 임베딩해 캐노니컬 후보 top-k 를 싸게 좁힌다.
   (전수 LLM 호출은 비싸니 임베딩으로 먼저 거른다.)
2) llm_verify — 좁혀진 후보만 Claude 가 정밀 재판정한다.
   (임베딩이 헷갈리는 의미 근접 쌍 cost_micros→CPC vs SPEND 를 잡는 자리.)

결과는 MappingProposal(canonical_key, confidence, reasoning, review_status).
"""
from __future__ import annotations

import json

from sentence_transformers import SentenceTransformer, util

from admeta import canonical
from admeta.config import get_settings
from admeta.models import ExtractedField, MappingProposal

_MODEL = "all-MiniLM-L6-v2"          # 영어 특화가 다국어보다 정확했음(측정 결과)
AUTO_TAU = 0.75                       # 이 이상이면 자동승인 후보


def _canon_text(f: canonical.CanonicalField) -> str:
    return f"{f.key.lower().replace('_', ' ')}. {f.description}"


def _field_text(f: ExtractedField) -> str:
    short = f.api_name.split(".")[-1].replace("_", " ")
    return f"{short}. {f.description}"


class EmbeddingRecall:
    """캐노니컬을 한 번 임베딩해두고 필드마다 top-k 후보를 반환."""

    def __init__(self, model_name: str = _MODEL):
        self.targets = canonical.ALL_FIELDS
        self.model = SentenceTransformer(model_name)
        self.emb = self.model.encode(
            [_canon_text(t) for t in self.targets],
            normalize_embeddings=True, show_progress_bar=False,
        )

    def candidates(self, field: ExtractedField, k: int = 3) -> list[tuple[str, float]]:
        q = self.model.encode(_field_text(field), normalize_embeddings=True)
        sims = util.cos_sim(q, self.emb)[0]
        idx = sims.argsort(descending=True)[:k]
        return [(self.targets[int(i)].key, float(sims[int(i)])) for i in idx]


_VERIFY_TOOL = {
    "name": "select_mapping",
    "description": "주어진 플랫폼 필드에 가장 맞는 표준(canonical) 개념을 후보 중에서 고른다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "canonical_key": {
                "type": "string",
                "description": "후보 중 정답 canonical key. 맞는 게 없으면 'NONE'.",
            },
            "confidence": {"type": "number", "description": "0~1 신뢰도"},
            "reasoning": {"type": "string", "description": "한 문장 근거"},
        },
        "required": ["canonical_key", "confidence", "reasoning"],
    },
}


def llm_verify(
    field: ExtractedField, candidates: list[tuple[str, float]], client, model: str
) -> MappingProposal:
    """후보 목록을 Claude 에게 주고 정밀 선택. 후보 설명도 함께 제시."""
    cand_lines = []
    for key, sim in candidates:
        cf = canonical.BY_KEY[key]
        cand_lines.append(f"- {key} ({cf.kind.value}): {cf.description} [임베딩유사도 {sim:.2f}]")
    prompt = (
        f"플랫폼 광고 필드를 표준 개념(canonical)에 매핑합니다.\n\n"
        f"[필드] {field.api_name} ({field.category})\n"
        f"설명: {field.description}\n\n"
        f"[후보 canonical 개념]\n" + "\n".join(cand_lines) + "\n\n"
        f"이 필드가 나타내는 개념과 정확히 일치하는 후보를 하나 고르세요. "
        f"의미가 다르면(예: 비용 vs 클릭당비용) 'NONE'."
    )
    resp = client.messages.create(
        model=model, max_tokens=300, temperature=0,  # 주간 재실행 시 결과 안정화
        tools=[_VERIFY_TOOL], tool_choice={"type": "tool", "name": "select_mapping"},
        messages=[{"role": "user", "content": prompt}],
    )
    data = next(b.input for b in resp.content if b.type == "tool_use")
    # LLM 이 'ROAS (derived)'처럼 kind 를 덧붙이는 경우 정규화 + 표준목록 검증
    raw_key = str(data["canonical_key"]).split("(")[0].strip().upper().replace(" ", "_")
    key = raw_key if raw_key in canonical.BY_KEY else "NONE"
    conf = float(data.get("confidence", 0.0))
    return MappingProposal(
        platform=field.source_url or "",
        api_name=field.api_name,
        canonical_key=None if key == "NONE" else key,
        confidence=conf,
        reasoning=data.get("reasoning", ""),
        review_status="approved" if conf >= AUTO_TAU else "proposed",
    )


def make_client():
    import anthropic
    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음 — backend/.env 에 추가하세요")
    return anthropic.Anthropic(api_key=s.anthropic_api_key), s.extract_model
