"""매핑 평가 — 임베딩 단독 vs 임베딩+LLM verify 정확도 비교.

canonical.py 의 씨딩 매핑을 ground truth 로 사용. 실행:
    py -3 -m admeta.normalize.eval_map
(ANTHROPIC_API_KEY 가 backend/.env 에 있어야 LLM 단계 실행)
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from admeta import canonical
from admeta.models import ExtractedField
from admeta.normalize.mapper import EmbeddingRecall, llm_verify, make_client

_ALIAS = {"google": "google_ads", "meta": "meta"}


def _load_ground_truth(parsed_dir="data/parsed"):
    """(platform, api_name) -> ({정답 키들}, ExtractedField)."""
    parsed = {}
    for plat in ("google_ads", "meta"):
        for d in json.loads(Path(f"{parsed_dir}/{plat}.json").read_text(encoding="utf-8")):
            parsed[(plat, d["api_name"])] = ExtractedField(**d)
    gt = defaultdict(set)
    fields = {}
    for cf in canonical.ALL_FIELDS:
        for mp in cf.mappings:
            key = (_ALIAS.get(mp.platform, mp.platform), mp.api_name)
            if key in parsed:
                gt[key].add(cf.key)
                fields[key] = parsed[key]
    return gt, fields


def main() -> int:
    gt, fields = _load_ground_truth()
    n = len(gt)
    print(f"평가 쌍: {n}개\n임베딩 리콜 준비...")
    recall = EmbeddingRecall()

    client, model = make_client()
    print(f"LLM verify 모델: {model}\n")

    emb_ok = llm_ok = 0
    misses = []
    for (plat, api), true_keys in gt.items():
        field = fields[(plat, api)]
        cands = recall.candidates(field, k=3)
        emb_pred = cands[0][0]
        if emb_pred in true_keys:
            emb_ok += 1

        proposal = llm_verify(field, cands, client, model)
        llm_pred = proposal.canonical_key or "NONE"
        if llm_pred in true_keys:
            llm_ok += 1
        else:
            misses.append((plat, api, "/".join(true_keys), emb_pred, llm_pred, proposal.confidence))

    print(f"=== 임베딩 단독:      {emb_ok}/{n} = {emb_ok/n*100:.0f}% ===")
    print(f"=== 임베딩 + LLM:     {llm_ok}/{n} = {llm_ok/n*100:.0f}% ===\n")
    print("LLM 후에도 남은 오답:")
    for plat, api, true, ep, lp, conf in misses:
        print(f"   {plat:<11}{api[:24]:<25} 정답 {true:<18} 임베딩 {ep:<12} LLM {lp:<12} conf {conf:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
