from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from human_to_agent.domain.assessment import AssessmentFact, AssessmentSnapshot
from human_to_agent.domain.assets import CaseKind
from human_to_agent.domain.common import NonEmptyStr, require_aware_utc
from human_to_agent.domain.readiness import ReadinessResult


class Stage(IntEnum):
    stage1 = 1
    stage2 = 2
    stage3 = 3
    stage4 = 4
    stage5 = 5


class GateStatus(StrEnum):
    satisfied = "satisfied"
    gap = "gap"
    indeterminate = "indeterminate"


class GateCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: NonEmptyStr
    fact: AssessmentFact | None
    status: GateStatus
    evidence_refs: tuple[NonEmptyStr, ...]
    message: NonEmptyStr
    next_action: NonEmptyStr | None = None


class GateReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target: NonEmptyStr
    checks: tuple[GateCheck, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(check.status is GateStatus.satisfied for check in self.checks)


class StageTransition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    current: Stage
    target: Stage
    actor: NonEmptyStr
    at: datetime
    reason: NonEmptyStr
    reopened: bool

    @field_validator("at")
    @classmethod
    def at_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class _Requirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: NonEmptyStr
    fact: AssessmentFact
    message: NonEmptyStr
    next_action: NonEmptyStr


def _req(identifier: str, fact: AssessmentFact, message: str) -> _Requirement:
    return _Requirement(
        requirement_id=identifier,
        fact=fact,
        message=message,
        next_action=f"Provide direct evidence for {fact.value}.",
    )


_STAGE_REQUIREMENTS: dict[Stage, tuple[_Requirement, ...]] = {
    Stage.stage1: (
        _req("PR-8.6-REAL", AssessmentFact.real_task, "A real task is reproduced."),
        _req("PR-8.6-GOAL", AssessmentFact.basic_goal_understood, "The basic goal is understood."),
        _req("PR-8.6-INPUT", AssessmentFact.inputs_identified, "Inputs are identified."),
        _req("PR-8.6-OUTPUT", AssessmentFact.outputs_identified, "Outputs are identified."),
        _req(
            "PR-8.6-MOD",
            AssessmentFact.manual_modifications_recorded,
            "Manual changes are recorded.",
        ),
        _req("PR-8.6-UNKNOWN", AssessmentFact.initial_unknowns_recorded, "Initial Unknowns exist."),
        _req(
            "PR-8.5-BASE", AssessmentFact.time_baseline_recorded, "The human baseline is recorded."
        ),
        _req(
            "PR-8.5-SUCCESS",
            AssessmentFact.initial_success_criteria,
            "Initial success is explicit.",
        ),
        _req(
            "PR-8.6-OWNER", AssessmentFact.owner_confirmed_usable, "The result is confirmed usable."
        ),
    ),
    Stage.stage2: (
        _req(
            "PR-9.6-THIRD",
            AssessmentFact.third_party_understands_goal_output,
            "A third party understands the task.",
        ),
        _req("PR-9.6-CONTRACT", AssessmentFact.task_contract_exists, "A task contract exists."),
        _req("PR-9.6-SKILL", AssessmentFact.skill_prototype_exists, "A Skill prototype exists."),
        _req(
            "PR-9.6-RERUN", AssessmentFact.original_case_rerun, "The original case is reproduced."
        ),
        _req(
            "PR-9.6-MOD", AssessmentFact.manual_modifications_linked, "Manual changes are linked."
        ),
        _req(
            "PR-9.6-UNKNOWN", AssessmentFact.key_unknowns_classified, "Key Unknowns are classified."
        ),
        _req("PR-9.6-PLAN", AssessmentFact.next_case_plan_exists, "The next case set is planned."),
    ),
    Stage.stage3: (
        _req("PR-10.7-NORMAL", AssessmentFact.normal_paths_stable, "Normal paths are stable."),
        _req(
            "PR-10.7-FAIL",
            AssessmentFact.common_failures_detected,
            "Common failures are detectable.",
        ),
        _req("PR-10.7-EVAL", AssessmentFact.result_evaluable, "Results can be evaluated."),
        _req("PR-10.7-BOUND", AssessmentFact.skill_boundaries_clear, "Skill boundaries are clear."),
        _req(
            "PR-10.7-INDEPENDENT",
            AssessmentFact.independent_skill_run,
            "A non-creator ran the Skill.",
        ),
        _req("PR-10.5-UNKNOWN", AssessmentFact.key_unknowns_managed, "Key Unknowns are managed."),
        _req(
            "PR-10.5-VERSION",
            AssessmentFact.skill_version_explainable,
            "Version changes are explainable.",
        ),
    ),
    Stage.stage4: (
        _req("PR-11.6-E2E", AssessmentFact.end_to_end_harness_run, "An end-to-end case passes."),
        _req("PR-11.6-TRACE", AssessmentFact.steps_traceable, "Every step is traceable."),
        _req(
            "PR-11.3-GOAL",
            AssessmentFact.harness_goal_and_completion,
            "Harness completion is explicit.",
        ),
        _req("PR-11.3-CONTEXT", AssessmentFact.context_defined, "Context is defined."),
        _req("PR-11.3-STATE", AssessmentFact.state_defined, "State is defined."),
        _req("PR-11.3-POLICY", AssessmentFact.policies_defined, "Permissions are defined."),
        _req("PR-11.6-GATE", AssessmentFact.human_gates_defined, "Human Gates are defined."),
        _req(
            "PR-11.6-EXCEPTION", AssessmentFact.exceptions_defined, "Exception paths are defined."
        ),
        _req(
            "PR-11.3-LOCAL-EVAL", AssessmentFact.local_evaluators_defined, "Local evaluators exist."
        ),
        _req(
            "PR-11.3-FINAL-EVAL",
            AssessmentFact.final_evaluator_defined,
            "A final evaluator exists.",
        ),
        _req(
            "PR-11.4-AUTONOMY", AssessmentFact.autonomy_approved, "The autonomy level is approved."
        ),
        _req(
            "PR-11.6-NONCREATOR",
            AssessmentFact.noncreator_harness_run,
            "A non-creator ran the Harness.",
        ),
    ),
    Stage.stage5: (
        _req(
            "PR-12.4-CONCLUSION",
            AssessmentFact.loop_readiness_conclusion,
            "A Readiness conclusion exists.",
        ),
        _req(
            "PR-12.2-STOP",
            AssessmentFact.stop_recovery_escalation_defined,
            "Loop controls are defined.",
        ),
        _req(
            "PR-12.2-GATE",
            AssessmentFact.high_risk_actions_have_human_gates,
            "High-risk actions are gated.",
        ),
    ),
}


_RELEASE_REQUIREMENTS = (
    _req("PR-12.5-GOAL", AssessmentFact.business_goal_clear, "The business goal is clear."),
    _req(
        "PR-12.5-CONTRACT", AssessmentFact.task_contract_complete, "The task contract is complete."
    ),
    _req("PR-12.5-SKILL", AssessmentFact.core_skill_validated, "Core Skills are validated."),
    _req(
        "PR-12.5-HARNESS", AssessmentFact.end_to_end_harness_run, "The Harness passes end-to-end."
    ),
    _req("PR-12.5-UNKNOWN", AssessmentFact.unknowns_managed, "Unknowns are managed."),
    _req(
        "PR-12.5-BOUNDARY",
        AssessmentFact.input_output_state_boundaries_clear,
        "Inputs, outputs, state, and boundaries are clear.",
    ),
    _req("PR-12.5-EVAL", AssessmentFact.result_evaluable, "The result is evaluable."),
    _req(
        "PR-12.5-EXCEPTION",
        AssessmentFact.key_exceptions_detectable,
        "Key exceptions are detectable.",
    ),
    _req(
        "PR-12.5-GATE",
        AssessmentFact.high_risk_actions_have_human_gates,
        "High-risk actions have Human Gates.",
    ),
    _req(
        "PR-12.5-RECOVERY",
        AssessmentFact.stop_recovery_escalation_defined,
        "Stop, recovery, and escalation are defined.",
    ),
    _req(
        "PR-12.5-MAINTAIN",
        AssessmentFact.noncreator_can_maintain,
        "A non-creator can maintain the workspace.",
    ),
    _req(
        "PR-18.3-INDEPENDENT",
        AssessmentFact.noncreator_harness_run,
        "Independent reproduction is complete.",
    ),
    _req(
        "PR-18.3-READINESS",
        AssessmentFact.loop_readiness_conclusion,
        "A Loop Readiness result exists.",
    ),
)


def _assess_requirement(
    requirement: _Requirement,
    snapshot: AssessmentSnapshot,
) -> GateCheck:
    if requirement.fact not in snapshot.facts:
        return GateCheck(
            requirement_id=requirement.requirement_id,
            fact=requirement.fact,
            status=GateStatus.gap,
            evidence_refs=(),
            message=f"Missing: {requirement.message}",
            next_action=requirement.next_action,
        )
    evidence = snapshot.evidence.get(requirement.fact, ())
    if not evidence:
        return GateCheck(
            requirement_id=requirement.requirement_id,
            fact=requirement.fact,
            status=GateStatus.indeterminate,
            evidence_refs=(),
            message=f"Unproven: {requirement.message}",
            next_action=requirement.next_action,
        )
    return GateCheck(
        requirement_id=requirement.requirement_id,
        fact=requirement.fact,
        status=GateStatus.satisfied,
        evidence_refs=evidence,
        message=requirement.message,
    )


def _case_coverage(snapshot: AssessmentSnapshot) -> GateCheck:
    required = {CaseKind.normal, CaseKind.boundary, CaseKind.failure}
    if not required <= set(snapshot.evaluated_case_kinds):
        return GateCheck(
            requirement_id="PR-10.7-CASES",
            fact=None,
            status=GateStatus.gap,
            evidence_refs=(),
            message="Normal, boundary, and failure cases are required.",
            next_action="Run and evaluate all three case kinds.",
        )
    if len(snapshot.case_evaluation_refs) < 3:
        return GateCheck(
            requirement_id="PR-10.7-CASES",
            fact=None,
            status=GateStatus.indeterminate,
            evidence_refs=snapshot.case_evaluation_refs,
            message="Case kinds exist but three evaluations are not proven.",
            next_action="Record one evaluation per required case kind.",
        )
    return GateCheck(
        requirement_id="PR-10.7-CASES",
        fact=None,
        status=GateStatus.satisfied,
        evidence_refs=snapshot.case_evaluation_refs,
        message="Normal, boundary, and failure cases are evaluated.",
    )


def _readiness_check(snapshot: AssessmentSnapshot, minimum: ReadinessResult) -> GateCheck:
    if snapshot.readiness_result is None:
        return GateCheck(
            requirement_id="PR-12-READINESS",
            fact=None,
            status=GateStatus.gap,
            evidence_refs=(),
            message="No Loop Readiness assessment exists.",
            next_action="Assess all ten core and six supplemental dimensions.",
        )
    if not snapshot.readiness_evidence_refs:
        return GateCheck(
            requirement_id="PR-12-READINESS",
            fact=None,
            status=GateStatus.indeterminate,
            evidence_refs=(),
            message="The Loop Readiness conclusion has no direct evidence.",
            next_action="Record the Readiness assessment artifact.",
        )
    if snapshot.readiness_result.rank < minimum.rank:
        return GateCheck(
            requirement_id="PR-12-READINESS",
            fact=None,
            status=GateStatus.gap,
            evidence_refs=snapshot.readiness_evidence_refs,
            message=f"Readiness must be at least {minimum.value}.",
            next_action="Close the blocking Readiness dimensions.",
        )
    return GateCheck(
        requirement_id="PR-12-READINESS",
        fact=None,
        status=GateStatus.satisfied,
        evidence_refs=snapshot.readiness_evidence_refs,
        message=f"Readiness is at least {minimum.value}.",
    )


def assess_stage(target: Stage, snapshot: AssessmentSnapshot) -> GateReport:
    checks = [
        _assess_requirement(requirement, snapshot) for requirement in _STAGE_REQUIREMENTS[target]
    ]
    if target is Stage.stage3:
        checks.append(_case_coverage(snapshot))
    if target is Stage.stage5:
        checks.append(_readiness_check(snapshot, ReadinessResult.not_ready))
    return GateReport(target=target.name, checks=tuple(checks))


def assess_complete_release(snapshot: AssessmentSnapshot) -> GateReport:
    checks = [_assess_requirement(requirement, snapshot) for requirement in _RELEASE_REQUIREMENTS]
    checks.extend(
        (
            _case_coverage(snapshot),
            _readiness_check(snapshot, ReadinessResult.conditional_ready),
        )
    )
    return GateReport(target="complete_release", checks=tuple(checks))


def decide_stage_transition(
    current: Stage,
    target: Stage,
    report: GateReport,
    *,
    actor: str,
    at: datetime,
    reason: str,
) -> StageTransition:
    if target > current and not report.passed:
        raise ValueError("stage transition requires a passing gate report")
    if target > current and target - current > 1:
        raise ValueError("stages must advance one at a time")
    return StageTransition(
        current=current,
        target=target,
        actor=actor,
        at=at,
        reason=reason,
        reopened=target < current,
    )


STAGE_MODELS: dict[str, type[BaseModel]] = {
    "gate-report": GateReport,
    "stage-state": AssessmentSnapshot,
}


__all__ = [
    "AssessmentFact",
    "AssessmentSnapshot",
    "GateCheck",
    "GateReport",
    "GateStatus",
    "Stage",
    "StageTransition",
    "assess_complete_release",
    "assess_stage",
    "decide_stage_transition",
]
