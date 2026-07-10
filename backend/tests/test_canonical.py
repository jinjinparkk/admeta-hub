"""Canonical 사전 정합성 테스트 — 표준 사전이 깨지지 않았는지 보증."""
import re

import pytest

from admeta import canonical as C
from admeta.canonical import DataType, Kind


def test_no_duplicate_keys():
    keys = [f.key for f in C.ALL_FIELDS]
    assert len(keys) == len(set(keys)), "중복된 Canonical key 존재"


def test_keys_are_upper_snake():
    for f in C.ALL_FIELDS:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", f.key), f"key 형식 위반: {f.key}"


def test_derived_have_formula_others_dont():
    for f in C.ALL_FIELDS:
        if f.kind is Kind.DERIVED:
            assert f.formula, f"{f.key} derived인데 formula 없음"
        else:
            assert f.formula is None, f"{f.key} non-derived인데 formula 있음"


def test_derived_formula_references_known_keys():
    token = re.compile(r"[A-Z][A-Z0-9_]+")
    for f in C.ALL_FIELDS:
        if f.kind is not Kind.DERIVED:
            continue
        for ref in token.findall(f.formula):
            assert ref in C.BY_KEY, f"{f.key} formula가 미정의 key 참조: {ref}"


def test_metrics_and_dimensions_have_mappings():
    for f in C.METRICS + C.DIMENSIONS:
        assert f.mappings, f"{f.key} 매핑 없음"


def test_mapping_confidence_in_range():
    for f in C.ALL_FIELDS:
        for mp in f.mappings:
            assert 0.0 <= mp.confidence <= 1.0


def test_currency_metrics_have_unit():
    for f in C.METRICS:
        if f.data_type is DataType.CURRENCY:
            assert f.unit, f"{f.key} currency인데 unit 없음"


def test_platform_keys():
    """canonical 매핑의 플랫폼 키는 레지스트리 키(또는 google/meta 별칭)여야 함."""
    from admeta.platforms import PLATFORMS
    allowed = set(PLATFORMS) | {"google", "meta"}   # 'google'은 google_ads 별칭
    unknown = C.platform_keys() - allowed
    assert not unknown, f"레지스트리에 없는 플랫폼 키: {unknown}"


def test_get_is_case_insensitive():
    assert C.get("clicks").key == "CLICKS"
    with pytest.raises(KeyError):
        C.get("NOPE")
