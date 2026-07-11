from datetime import UTC, datetime

import pytest

from human_to_agent.domain.readiness import (
    AutonomyLevel,
    DimensionAssessment,
    ReadinessDimension,
    ReadinessFacts,
    ReadinessResult,
    assess_readiness,
    default_readiness_policy,
    record_autonomy_approval,
)


def satisfied_facts() -> ReadinessFacts:
    return ReadinessFacts(
        assessment_id="readiness.pilot",
        workspace_id="ws-pilot",
        dimensions={
            dimension: DimensionAssessment.satisfied(
                dimension,
                evidence_refs=(f"ev-{dimension.value}",),
            )
            for dimension in ReadinessDimension
        },
        production_evidence_refs=(),
    )


def test_all_ten_core_and_six_supplemental_dimensions_are_assessed() -> None:
    assessment = assess_readiness(satisfied_facts(), default_readiness_policy())
    assert set(assessment.dimensions) == set(ReadinessDimension)
    assert len(assessment.dimensions) == 16
    assert assessment.result is ReadinessResult.bounded_ready


def test_missing_dimension_is_indeterminate_and_blocks_conditional_ready() -> None:
    facts = satisfied_facts()
    dimensions = dict(facts.dimensions)
    del dimensions[ReadinessDimension.evaluator]
    assessment = assess_readiness(
        facts.model_copy(update={"dimensions": dimensions}),
        default_readiness_policy(),
    )
    assert assessment.result is ReadinessResult.not_ready
    assert assessment.dimensions[ReadinessDimension.evaluator].is_indeterminate
    assert "evaluator" in " ".join(assessment.evidence_gaps)


def test_indeterminate_core_dimension_prevents_conditional_ready() -> None:
    facts = satisfied_facts().with_dimension(
        ReadinessDimension.evaluator,
        DimensionAssessment.indeterminate(
            ReadinessDimension.evaluator,
            "No independent result",
        ),
    )
    assessment = assess_readiness(facts, default_readiness_policy())
    assert assessment.result is ReadinessResult.not_ready
    assert assessment.evidence_gaps
    assert assessment.risks


def test_supplemental_gap_retains_conditional_result_and_caps_autonomy() -> None:
    facts = satisfied_facts().with_dimension(
        ReadinessDimension.tool_connector_availability,
        DimensionAssessment.gap(
            ReadinessDimension.tool_connector_availability,
            "Connector contract is not validated",
            risks=("Action availability is uncertain",),
            next_action="Validate the Tool Registry contract.",
        ),
    )
    assessment = assess_readiness(facts, default_readiness_policy())
    assert assessment.result is ReadinessResult.conditional_ready
    assert assessment.recommended_ceiling is AutonomyLevel.h1
    assert "Action availability is uncertain" in assessment.risks


def test_recommendation_never_auto_approves_autonomy() -> None:
    assessment = assess_readiness(satisfied_facts(), default_readiness_policy())
    assert assessment.approved_autonomy is None
    with pytest.raises(ValueError, match="owner"):
        record_autonomy_approval(
            assessment,
            AutonomyLevel.h3,
            owner_id="",
            at=datetime(2026, 7, 10, tzinfo=UTC),
            evidence_refs=("ev-owner",),
        )


def test_owner_cannot_approve_above_recommended_ceiling() -> None:
    facts = satisfied_facts().with_dimension(
        ReadinessDimension.independent_verifier,
        DimensionAssessment.gap(
            ReadinessDimension.independent_verifier,
            "Independent verifier has not run",
        ),
    )
    assessment = assess_readiness(facts, default_readiness_policy())
    with pytest.raises(ValueError, match="ceiling"):
        record_autonomy_approval(
            assessment,
            AutonomyLevel.h5,
            owner_id="owner",
            at=datetime(2026, 7, 10, tzinfo=UTC),
            evidence_refs=("ev-owner",),
        )


def test_readiness_rank_is_monotonic_but_not_a_score() -> None:
    assert [item.rank for item in ReadinessResult] == [0, 1, 2, 3, 4]
