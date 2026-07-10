from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType

BASE = {
    "schema_version": "1",
    "id": "ev-rule-1",
    "workspace_id": "ws-pilot",
    "revision": 1,
    "status": "active",
    "owners": ("business-owner",),
    "created_at": datetime(2026, 7, 10, tzinfo=UTC),
    "updated_at": datetime(2026, 7, 10, tzinfo=UTC),
    "provenance": "human",
    "links": (),
    "evidence_refs": (),
    "type": EvidenceType.formal_rule,
    "source": "PR/Harness Foundry PR.md",
    "locator": "§10.4",
    "captured_by": "requirements-reviewer",
    "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
    "content_summary": "The PR requires evidence-backed Unknown closure.",
    "claim": "Unknown closure requires evidence",
    "basis": EvidenceBasis.observed,
    "applicability_scope": ("Harness Foundry workspaces",),
    "validity_conditions": ("PR remains normative",),
    "invalidation_conditions": ("The Owner supersedes PR §10.4",),
    "content_sha256": "0" * 64,
}


def test_low_confidence_claim_requires_cheapest_probe() -> None:
    with pytest.raises(ValidationError, match="cheapest_probe"):
        Evidence.model_validate(BASE | {"basis": EvidenceBasis.assumption})


def test_low_confidence_claim_accepts_a_concrete_probe() -> None:
    evidence = Evidence.model_validate(
        BASE
        | {
            "basis": EvidenceBasis.unverified,
            "cheapest_probe": "Ask the business Owner to confirm PR §10.4.",
        }
    )
    assert evidence.cheapest_probe is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", ""),
        ("locator", ""),
        ("captured_by", ""),
        ("content_summary", ""),
        ("applicability_scope", ()),
        ("validity_conditions", ()),
        ("invalidation_conditions", ()),
        ("content_sha256", "not-a-sha"),
    ],
)
def test_evidence_requires_exact_source_and_validity(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Evidence.model_validate(BASE | {field: value})


def test_metadata_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Evidence.model_validate(BASE | {"captured_at": datetime(2026, 7, 10)})
