from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from harness_foundry.domain.common import AssetMetadata, NonEmptyStr, require_aware_utc


class CaseKind(StrEnum):
    normal = "normal"
    boundary = "boundary"
    failure = "failure"
    golden = "golden"


class EvaluationResult(StrEnum):
    passed = "passed"
    failed = "failed"
    indeterminate = "indeterminate"


class ActionClass(StrEnum):
    read_only = "read_only"
    internal_write = "internal_write"
    external_send = "external_send"
    irreversible = "irreversible"
    forbidden = "forbidden"


class ContextKind(StrEnum):
    fixed = "fixed"
    task = "task"
    organizational = "organizational"
    preference = "preference"
    historical = "historical"
    ephemeral = "ephemeral"


class HumanGateDecisionKind(StrEnum):
    approve = "approve"
    reject = "reject"
    modify = "modify"


class WorkspaceManifest(AssetMetadata):
    name: NonEmptyStr
    purpose: NonEmptyStr
    current_stage: int = Field(ge=1, le=5)
    risk_level: NonEmptyStr
    owner_id: NonEmptyStr
    autonomy_level: NonEmptyStr


class TaskContract(AssetMetadata):
    business_goal: NonEmptyStr
    inputs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    outputs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    preconditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    steps: tuple[NonEmptyStr, ...] = Field(min_length=1)
    rules: tuple[NonEmptyStr, ...] = Field(min_length=1)
    human_judgment_points: tuple[NonEmptyStr, ...]
    acceptance_criteria: tuple[NonEmptyStr, ...] = Field(min_length=1)
    known_exceptions: tuple[NonEmptyStr, ...]
    prohibited_actions: tuple[NonEmptyStr, ...]
    applies_when: tuple[NonEmptyStr, ...] = Field(min_length=1)
    does_not_apply_when: tuple[NonEmptyStr, ...] = Field(min_length=1)
    owner_id: NonEmptyStr


class SkillSpec(AssetMetadata):
    goal: NonEmptyStr
    inputs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    outputs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    preconditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    applies_when: tuple[NonEmptyStr, ...] = Field(min_length=1)
    does_not_apply_when: tuple[NonEmptyStr, ...] = Field(min_length=1)
    dependencies: tuple[NonEmptyStr, ...]
    evaluator_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    error_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    stop_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    case_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)


class CaseRecord(AssetMetadata):
    kind: CaseKind
    skill_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    input_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    expected_output: NonEmptyStr
    evaluator_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)


class EvaluationRecord(AssetMetadata):
    subject_ref: NonEmptyStr
    case_ref: NonEmptyStr
    evaluator_id: NonEmptyStr
    result: EvaluationResult
    actual_output_ref: NonEmptyStr
    criteria_results: tuple[NonEmptyStr, ...] = Field(min_length=1)


class WorkflowSpec(AssetMetadata):
    goal: NonEmptyStr
    skill_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    steps: tuple[dict[str, object], ...] = Field(min_length=1)
    state_model_ref: NonEmptyStr
    policy_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    human_gate_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    exception_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    final_evaluator_ref: NonEmptyStr


class HarnessSpec(AssetMetadata):
    goal: NonEmptyStr
    execution_loop_ref: NonEmptyStr
    tool_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    context_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    state_model_ref: NonEmptyStr
    lifecycle_hooks: tuple[NonEmptyStr, ...] = Field(min_length=1)
    evaluator_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    workflow_ref: NonEmptyStr


class ToolSpec(AssetMetadata):
    name: NonEmptyStr
    input_schema_ref: NonEmptyStr
    output_schema_ref: NonEmptyStr
    action_class: ActionClass
    required_permissions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    side_effects: tuple[NonEmptyStr, ...] = Field(min_length=1)
    idempotent: bool
    retry_semantics: NonEmptyStr
    human_gate_ref: NonEmptyStr | None = None
    executable_adapter: NonEmptyStr | None = None

    @model_validator(mode="after")
    def enforce_action_boundary(self) -> ToolSpec:
        if (
            self.action_class in {ActionClass.external_send, ActionClass.irreversible}
            and self.human_gate_ref is None
        ):
            raise ValueError("human_gate_ref is required for external or irreversible tools")
        if self.action_class is ActionClass.forbidden and self.executable_adapter is not None:
            raise ValueError("forbidden tools cannot define executable_adapter")
        return self


class ContextSpec(AssetMetadata):
    kind: ContextKind
    source_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    retention: NonEmptyStr
    allowed_usage: tuple[NonEmptyStr, ...] = Field(min_length=1)


class StateTransition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: NonEmptyStr
    target: NonEmptyStr
    event: NonEmptyStr
    guard: NonEmptyStr | None = None


class StateModelSpec(AssetMetadata):
    states: tuple[NonEmptyStr, ...] = Field(min_length=1)
    initial_state: NonEmptyStr
    terminal_states: tuple[NonEmptyStr, ...] = Field(min_length=1)
    transitions: tuple[StateTransition, ...] = Field(min_length=1)
    checkpoint_policy: NonEmptyStr
    persistence: NonEmptyStr
    restore_semantics: NonEmptyStr

    @model_validator(mode="after")
    def state_references_exist(self) -> StateModelSpec:
        known = set(self.states)
        referenced = {self.initial_state, *self.terminal_states}
        referenced.update(item.source for item in self.transitions)
        referenced.update(item.target for item in self.transitions)
        if not referenced <= known:
            raise ValueError("state transition references an unknown state")
        return self


class EvaluatorSpec(AssetMetadata):
    independent_inputs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    pass_signals: tuple[NonEmptyStr, ...] = Field(min_length=1)
    fail_signals: tuple[NonEmptyStr, ...] = Field(min_length=1)
    indeterminate_signals: tuple[NonEmptyStr, ...] = Field(min_length=1)
    acceptable_deviation: tuple[NonEmptyStr, ...]
    evidence_output: NonEmptyStr


class PolicySpec(AssetMetadata):
    rules: tuple[NonEmptyStr, ...] = Field(min_length=1)
    permitted_action_classes: tuple[ActionClass, ...] = Field(min_length=1)
    human_gate_refs: tuple[NonEmptyStr, ...]


class HumanGateSpec(AssetMetadata):
    action_classes: tuple[ActionClass, ...] = Field(min_length=1)
    approver_roles: tuple[NonEmptyStr, ...] = Field(min_length=1)
    required_evidence: tuple[NonEmptyStr, ...] = Field(min_length=1)
    rejection_behavior: NonEmptyStr
    recovery_entry: NonEmptyStr


class ActionPackage(AssetMetadata):
    tool_ref: NonEmptyStr
    action_class: ActionClass
    inputs: dict[str, object] = Field(min_length=1)
    expected_side_effects: tuple[NonEmptyStr, ...] = Field(min_length=1)
    idempotency_key: NonEmptyStr
    human_gate_ref: NonEmptyStr
    executed: Literal[False] = False


class HumanGateDecision(AssetMetadata):
    action_package_ref: NonEmptyStr
    decision: HumanGateDecisionKind
    actor_id: NonEmptyStr
    decided_at: datetime
    recovery_entry: NonEmptyStr
    run_ref: NonEmptyStr
    unknown_ref: NonEmptyStr | None = None
    modified_action_ref: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_decision_links(self) -> HumanGateDecision:
        object.__setattr__(self, "decided_at", require_aware_utc(self.decided_at))
        if self.decision is HumanGateDecisionKind.reject and self.unknown_ref is None:
            raise ValueError("unknown_ref is required for a rejected action")
        if self.decision is HumanGateDecisionKind.modify and self.modified_action_ref is None:
            raise ValueError("modified_action_ref is required for a modified action")
        return self


class ExceptionSpec(AssetMetadata):
    trigger: NonEmptyStr
    response: NonEmptyStr
    escalation: NonEmptyStr
    retry_semantics: NonEmptyStr
    stop_condition: NonEmptyStr
    creates_unknown: bool


class RunRecord(AssetMetadata):
    actor_id: NonEmptyStr
    actor_role: NonEmptyStr
    input_tree_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    steps: tuple[NonEmptyStr, ...] = Field(min_length=1)
    skill_ref: NonEmptyStr | None = None
    case_ref: NonEmptyStr | None = None
    workflow_ref: NonEmptyStr | None = None
    evaluation_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    passed: bool


ASSET_MODELS: dict[str, type[AssetMetadata]] = {
    "action-package": ActionPackage,
    "case": CaseRecord,
    "context": ContextSpec,
    "evaluation": EvaluationRecord,
    "evaluator": EvaluatorSpec,
    "exception": ExceptionSpec,
    "harness": HarnessSpec,
    "human-gate": HumanGateSpec,
    "human-gate-decision": HumanGateDecision,
    "policy": PolicySpec,
    "run": RunRecord,
    "skill": SkillSpec,
    "state-model": StateModelSpec,
    "task-contract": TaskContract,
    "tool": ToolSpec,
    "workflow": WorkflowSpec,
    "workspace": WorkspaceManifest,
}
