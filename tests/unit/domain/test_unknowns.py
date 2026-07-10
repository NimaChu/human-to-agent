from datetime import UTC, datetime

import pytest

from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from harness_foundry.domain.unknowns import (
    Unknown,
    UnknownCategory,
    UnknownClosure,
    UnknownDisposition,
    UnknownStatus,
    close_unknown,
    reopen_unknown,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)
META = {
    "schema_version": "1",
    "workspace_id": "ws-pilot",
    "revision": 1,
    "status": "active",
    "owners": ("owner",),
    "created_at": NOW,
    "updated_at": NOW,
    "provenance": "human",
    "links": (),
    "evidence_refs": (),
}


def evidence(
    evidence_id: str = "ev-rule", kind: EvidenceType = EvidenceType.formal_rule
) -> Evidence:
    return Evidence.model_validate(
        META
        | {
            "id": evidence_id,
            "type": kind,
            "source": "PR/Harness Foundry PR.md",
            "locator": "§10.4",
            "captured_by": "reviewer",
            "captured_at": NOW,
            "content_summary": "Unknown closure requires evidence.",
            "claim": "The rule is confirmed",
            "basis": EvidenceBasis.observed,
            "applicability_scope": ("ws-pilot",),
            "validity_conditions": ("PR remains normative",),
            "invalidation_conditions": ("Owner supersedes the rule",),
            "content_sha256": "1" * 64,
        }
    )


def unknown() -> Unknown:
    return Unknown.model_validate(
        META
        | {
            "id": "unknown.rule-priority",
            "title": "Rule priority is unclear",
            "description": "Two rules can conflict.",
            "category": UnknownCategory.rule,
            "unknown_status": UnknownStatus.evidence,
            "impact_dimensions": ("correctness", "automation-boundary"),
            "impact_narrative": "The wrong rule may be applied.",
            "occurrence_conditions": ("Two rules match",),
            "affected_assets": ("skill.extract",),
            "confidence_basis": EvidenceBasis.unverified,
            "owner_id": "owner",
            "expected_responder_role": "business-owner",
            "cheapest_probe": "Ask the Owner using one conflict case.",
            "prompt_patch": "Stop and request rule precedence when two rules match.",
            "automation_restriction": "Remain human-only on conflicting rules.",
            "allowed_closure_evidence": (EvidenceType.formal_rule,),
            "fact_resolved": False,
        }
    )


def closure(disposition: UnknownDisposition = UnknownDisposition.resolved) -> UnknownClosure:
    return UnknownClosure(
        disposition=disposition,
        owner_id="owner",
        actor="owner",
        at=NOW,
        conclusion="Rule A takes precedence.",
        impact="Skill and evaluator updated.",
        evidence_refs=("ev-rule",),
        propagated_to=("skill.extract", "eval.extract"),
    )


def test_close_requires_allowed_evidence_owner_and_propagation() -> None:
    item = unknown()
    proof = evidence()
    with pytest.raises(ValueError, match="owner"):
        close_unknown(
            item, closure().model_copy(update={"owner_id": "different"}), {proof.id: proof}
        )
    with pytest.raises(ValueError, match="propagation"):
        close_unknown(item, closure().model_copy(update={"propagated_to": ()}), {proof.id: proof})


def test_close_rejects_missing_or_disallowed_evidence() -> None:
    item = unknown()
    with pytest.raises(ValueError, match="missing evidence"):
        close_unknown(item, closure(), {})

    proof = evidence(kind=EvidenceType.historical_data)
    with pytest.raises(ValueError, match="allowed evidence"):
        close_unknown(item, closure(), {"ev-rule": proof})


def test_accepted_risk_is_managed_not_known() -> None:
    item = unknown()
    proof = evidence()
    managed = close_unknown(
        item,
        closure(UnknownDisposition.accepted_risk),
        {proof.id: proof},
    )
    assert managed.unknown_status is UnknownStatus.accepted_risk
    assert managed.fact_resolved is False
    assert managed.history[-1].to_status is UnknownStatus.accepted_risk


def test_resolved_closure_marks_fact_resolved() -> None:
    item = unknown()
    proof = evidence()
    resolved = close_unknown(item, closure(), {proof.id: proof})
    assert resolved.unknown_status is UnknownStatus.resolved
    assert resolved.fact_resolved is True


def test_reopen_preserves_closure_and_appends_history() -> None:
    item = unknown()
    proof = evidence()
    closed = close_unknown(item, closure(), {proof.id: proof})
    reopened = reopen_unknown(
        closed,
        reason="A contradictory case appeared",
        actor="reviewer",
        at=NOW,
        evidence_refs=("ev-contradiction",),
    )
    assert reopened.unknown_status is UnknownStatus.reopened
    assert reopened.closure == closed.closure
    assert reopened.fact_resolved is False
    assert reopened.history[-1].reason == "A contradictory case appeared"
    assert reopened.history[-1].evidence_refs == ("ev-contradiction",)


def test_unknown_model_carries_discovery_and_automation_controls() -> None:
    item = unknown()
    assert item.cheapest_probe
    assert item.prompt_patch
    assert item.occurrence_conditions
    assert item.automation_restriction
