from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from human_to_agent.domain.assets import CaseKind
from human_to_agent.domain.common import NonEmptyStr
from human_to_agent.domain.readiness import ReadinessResult


class AssessmentFact(StrEnum):
    real_task = "real_task"
    basic_goal_understood = "basic_goal_understood"
    inputs_identified = "inputs_identified"
    outputs_identified = "outputs_identified"
    manual_modifications_recorded = "manual_modifications_recorded"
    initial_unknowns_recorded = "initial_unknowns_recorded"
    time_baseline_recorded = "time_baseline_recorded"
    initial_success_criteria = "initial_success_criteria"
    owner_confirmed_usable = "owner_confirmed_usable"

    third_party_understands_goal_output = "third_party_understands_goal_output"
    task_contract_exists = "task_contract_exists"
    skill_prototype_exists = "skill_prototype_exists"
    original_case_rerun = "original_case_rerun"
    manual_modifications_linked = "manual_modifications_linked"
    key_unknowns_classified = "key_unknowns_classified"
    next_case_plan_exists = "next_case_plan_exists"

    normal_paths_stable = "normal_paths_stable"
    common_failures_detected = "common_failures_detected"
    result_evaluable = "result_evaluable"
    skill_boundaries_clear = "skill_boundaries_clear"
    independent_skill_run = "independent_skill_run"
    key_unknowns_managed = "key_unknowns_managed"
    skill_version_explainable = "skill_version_explainable"

    end_to_end_harness_run = "end_to_end_harness_run"
    steps_traceable = "steps_traceable"
    harness_goal_and_completion = "harness_goal_and_completion"
    context_defined = "context_defined"
    state_defined = "state_defined"
    policies_defined = "policies_defined"
    human_gates_defined = "human_gates_defined"
    exceptions_defined = "exceptions_defined"
    local_evaluators_defined = "local_evaluators_defined"
    final_evaluator_defined = "final_evaluator_defined"
    autonomy_approved = "autonomy_approved"
    noncreator_harness_run = "noncreator_harness_run"

    business_goal_clear = "business_goal_clear"
    task_contract_complete = "task_contract_complete"
    core_skill_validated = "core_skill_validated"
    unknowns_managed = "unknowns_managed"
    input_output_state_boundaries_clear = "input_output_state_boundaries_clear"
    key_exceptions_detectable = "key_exceptions_detectable"
    high_risk_actions_have_human_gates = "high_risk_actions_have_human_gates"
    stop_recovery_escalation_defined = "stop_recovery_escalation_defined"
    noncreator_can_maintain = "noncreator_can_maintain"
    loop_readiness_conclusion = "loop_readiness_conclusion"


class AssessmentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: NonEmptyStr
    current_stage: int = Field(ge=1, le=5)
    facts: frozenset[AssessmentFact]
    evidence: dict[AssessmentFact, tuple[NonEmptyStr, ...]]
    evaluated_case_kinds: frozenset[CaseKind]
    case_evaluation_refs: tuple[NonEmptyStr, ...]
    skill_count: int = Field(ge=0)
    readiness_result: ReadinessResult | None
    readiness_evidence_refs: tuple[NonEmptyStr, ...]

    def without_fact(self, fact: AssessmentFact) -> AssessmentSnapshot:
        facts = set(self.facts)
        facts.discard(fact)
        evidence = dict(self.evidence)
        evidence.pop(fact, None)
        return self.model_copy(update={"facts": frozenset(facts), "evidence": evidence})

    def without_evidence(self, fact: AssessmentFact) -> AssessmentSnapshot:
        evidence = dict(self.evidence)
        evidence.pop(fact, None)
        return self.model_copy(update={"evidence": evidence})
