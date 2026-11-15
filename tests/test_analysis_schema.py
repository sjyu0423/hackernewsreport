"""Structured analysis validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from qwennews.analysis_schema import ArticleAnalysis, EvidenceSufficiency
from qwennews.analyze import extract_json_object, validate_analysis_payload

VALID = {
    "article_id": "abc12345deadbeef",
    "category": "tooling",
    "summary": "A stable release improves local inference packaging and compatibility.",
    "why_it_matters": "Local AI developers get a clearer baseline for deploying GGUF models.",
    "relevance_score": 4,
    "significance_score": 3,
    "evidence_sufficiency": "sufficient",
    "key_claims": ["Version 1.0.0 is presented as a stable release."],
    "limitations": "Release notes may omit performance benchmarks.",
}


def test_valid_analysis_model() -> None:
    model = ArticleAnalysis.model_validate(VALID)
    assert model.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT
    assert model.relevance_score == 4


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.update(relevance_score=9),
        lambda d: d.update(significance_score=0),
        lambda d: d.update(summary="too short"),
        lambda d: d.update(evidence_sufficiency="nope"),
        lambda d: d.update(key_claims=["x"] * 20),
    ],
)
def test_invalid_analysis_rejected(mutator) -> None:
    payload = dict(VALID)
    mutator(payload)
    with pytest.raises(ValidationError):
        ArticleAnalysis.model_validate(payload)


def test_validate_rebinds_article_id() -> None:
    payload = dict(VALID)
    payload["article_id"] = "model-invented-id-zzzz"
    model = validate_analysis_payload(payload, expected_article_id="abc12345deadbeef")
    assert model.article_id == "abc12345deadbeef"


def test_extract_json_object_from_fence() -> None:
    text = 'Here you go:\n```json\n{"ok": true, "n": 1}\n```\n'
    assert extract_json_object(text) == {"ok": True, "n": 1}
