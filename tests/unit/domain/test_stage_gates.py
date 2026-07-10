from datetime import UTC, datetime

import pytest

from harness_foundry.domain.assets import CaseKind
from harness_foundry.domain.readiness import ReadinessResult
from harness_foundry.domain.stages import (
    AssessmentFact,
    AssessmentSnapshot,
    GateStatus,
    Stage,
    assess_complete_release,
    assess_stage,
    decide_stage_transition,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def complete_snapshot() -> AssessmentSnapshot:
    facts = frozenset(AssessmentFact)
    return AssessmentSnapshot(
        workspace_id="ws-pilot",
        current_stage=Stage.stage4,
        facts=facts,
        evidence={fact: (f"ev-{fact.value}",) for fact in facts},
        evaluated_case_kinds=frozenset({CaseKind.normal, CaseKind.boundary, CaseKind.failure}),
        case_evaluation_refs=("eval.normal", "eval.boundary", "eval.failure"),
        skill_count=1,
        readiness_result=ReadinessResult.bounded_ready,
        readiness_evidence_refs=("readiness.pilot",),
    )


@pytest.mark.parametrize(
    "missing",
    [
        AssessmentFact.real_task,
        AssessmentFact.inputs_identified,
        AssessmentFact.outputs_identified,
        AssessmentFact.manual_modifications_recorded,
        AssessmentFact.initial_unknowns_recorded,
        AssessmentFact.time_baseline_recorded,
        AssessmentFact.initial_success_criteria,
        AssessmentFact.owner_confirmed_usable,
    ],
)
def test_stage1_requires_real_trace_baseline_unknown_and_owner(missing: AssessmentFact) -> None:
    snapshot = complete_snapshot().without_fact(missing)
    assert assess_stage(Stage.stage1, snapshot).passed is False


@pytest.mark.parametrize(
    "missing",
    [
        AssessmentFact.third_party_understands_goal_output,
        AssessmentFact.task_contract_exists,
        AssessmentFact.skill_prototype_exists,
        AssessmentFact.original_case_rerun,
        AssessmentFact.manual_modifications_linked,
        AssessmentFact.key_unknowns_classified,
        AssessmentFact.next_case_plan_exists,
    ],
)
def test_stage2_requires_contract_skill_rerun_and_case_plan(missing: AssessmentFact) -> None:
    snapshot = complete_snapshot().without_fact(missing)
    assert assess_stage(Stage.stage2, snapshot).passed is False


def test_stage3_requires_normal_boundary_failure_cases_and_independent_review() -> None:
    snapshot = complete_snapshot().model_copy(
        update={
            "evaluated_case_kinds": frozenset({CaseKind.normal, CaseKind.boundary}),
            "case_evaluation_refs": ("eval.normal", "eval.boundary"),
        }
    )
    report = assess_stage(Stage.stage3, snapshot)
    assert report.passed is False
    assert (
        next(check for check in report.checks if check.requirement_id == "PR-10.7-CASES").status
        is GateStatus.gap
    )


def test_stage4_single_skill_still_requires_complete_harness_controls() -> None:
    snapshot = complete_snapshot().without_fact(AssessmentFact.human_gates_defined)
    assert snapshot.skill_count == 1
    assert assess_stage(Stage.stage4, snapshot).passed is False
    assert assess_stage(Stage.stage4, complete_snapshot()).passed is True


def test_stage5_requires_readiness_assessment() -> None:
    snapshot = complete_snapshot().model_copy(
        update={"readiness_result": None, "readiness_evidence_refs": ()}
    )
    assert assess_stage(Stage.stage5, snapshot).passed is False


def test_release_requires_pr_12_5_18_3_and_conditional_ready() -> None:
    snapshot = complete_snapshot().model_copy(
        update={"readiness_result": ReadinessResult.not_ready}
    )
    assert assess_complete_release(snapshot).passed is False
    assert assess_complete_release(complete_snapshot()).passed is True


def test_indeterminate_gate_cannot_advance() -> None:
    snapshot = complete_snapshot().without_evidence(AssessmentFact.task_contract_exists)
    report = assess_stage(Stage.stage2, snapshot)
    check = next(item for item in report.checks if item.fact is AssessmentFact.task_contract_exists)
    assert check.status is GateStatus.indeterminate
    with pytest.raises(ValueError, match="gate report"):
        decide_stage_transition(
            Stage.stage1,
            Stage.stage2,
            report,
            actor="owner",
            at=NOW,
            reason="Advance",
        )


def test_new_evidence_can_reopen_an_earlier_stage() -> None:
    report = assess_stage(Stage.stage3, complete_snapshot())
    transition = decide_stage_transition(
        Stage.stage4,
        Stage.stage3,
        report,
        actor="reviewer",
        at=NOW,
        reason="A contradictory case invalidated the Skill boundary.",
    )
    assert transition.reopened is True
    assert transition.target is Stage.stage3
