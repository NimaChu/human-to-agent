from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from harness_foundry.domain.assets import (
    ActionClass,
    ActionPackage,
    CaseKind,
    CaseRecord,
    HarnessSpec,
    HumanGateDecision,
    HumanGateDecisionKind,
    SkillSpec,
    ToolSpec,
    WorkflowSpec,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)
META: dict[str, Any] = {
    "schema_version": "1",
    "workspace_id": "ws-pilot",
    "revision": 1,
    "status": "active",
    "owners": ("owner",),
    "created_at": NOW,
    "updated_at": NOW,
    "provenance": "human",
    "links": (),
    "evidence_refs": ("ev-owner",),
}


def valid_skill() -> dict[str, Any]:
    return META | {
        "id": "skill.extract",
        "goal": "Extract normative requirements",
        "inputs": ("PR document",),
        "outputs": ("Requirement inventory",),
        "preconditions": ("Source is readable",),
        "applies_when": ("A normative source is supplied",),
        "does_not_apply_when": ("The source is only illustrative",),
        "dependencies": ("tool.read-file",),
        "evaluator_refs": ("eval.requirement-map",),
        "error_conditions": ("Source locator is missing",),
        "stop_conditions": ("Every source section is classified",),
        "case_refs": ("case.mainline",),
    }


@pytest.mark.parametrize(
    "field",
    [
        "applies_when",
        "does_not_apply_when",
        "evaluator_refs",
        "error_conditions",
        "stop_conditions",
    ],
)
def test_skill_requires_boundary_evaluation_and_stop_semantics(field: str) -> None:
    with pytest.raises(ValidationError):
        SkillSpec(**(valid_skill() | {field: ()}))


def test_case_requires_expected_output() -> None:
    with pytest.raises(ValidationError):
        CaseRecord(
            **(
                META
                | {
                    "id": "case.mainline",
                    "kind": CaseKind.normal,
                    "skill_refs": ("skill.extract",),
                    "input_refs": ("PR/Harness Foundry PR.md",),
                    "expected_output": "",
                    "evaluator_refs": ("eval.requirement-map",),
                }
            )
        )


def test_workflow_requires_state_policy_gates_exceptions_and_final_evaluator() -> None:
    with pytest.raises(ValidationError):
        WorkflowSpec(
            **(
                META
                | {
                    "id": "workflow.main",
                    "goal": "Build a child workspace",
                    "skill_refs": ("skill.extract",),
                    "steps": ({"id": "extract", "skill_ref": "skill.extract"},),
                    "state_model_ref": "state.main",
                    "policy_refs": (),
                    "human_gate_refs": ("gate.owner",),
                    "exception_refs": ("exception.source",),
                    "final_evaluator_ref": "eval.release",
                }
            )
        )


def test_external_tool_requires_typed_contract_and_human_gate() -> None:
    with pytest.raises(ValidationError, match="human_gate_ref"):
        ToolSpec(
            **(
                META
                | {
                    "id": "tool.send",
                    "name": "send",
                    "input_schema_ref": "schema.action-input",
                    "output_schema_ref": "schema.action-output",
                    "action_class": ActionClass.external_send,
                    "required_permissions": ("external.send",),
                    "side_effects": ("Sends a message",),
                    "idempotent": False,
                    "retry_semantics": "No automatic retry",
                }
            )
        )


def test_forbidden_tool_cannot_have_executable_adapter() -> None:
    with pytest.raises(ValidationError, match="executable_adapter"):
        ToolSpec(
            **(
                META
                | {
                    "id": "tool.delete",
                    "name": "delete",
                    "input_schema_ref": "schema.delete-input",
                    "output_schema_ref": "schema.delete-output",
                    "action_class": ActionClass.forbidden,
                    "required_permissions": ("never",),
                    "side_effects": ("Deletes data",),
                    "idempotent": False,
                    "retry_semantics": "Never execute",
                    "executable_adapter": "adapter.delete",
                }
            )
        )


def test_harness_requires_all_execution_tool_context_state_hook_evaluator_refs() -> None:
    with pytest.raises(ValidationError):
        HarnessSpec(
            **(
                META
                | {
                    "id": "harness.main",
                    "goal": "Build a workspace",
                    "execution_loop_ref": "workflow.main",
                    "tool_refs": (),
                    "context_refs": ("context.main",),
                    "state_model_ref": "state.main",
                    "lifecycle_hooks": ("hook.audit",),
                    "evaluator_refs": ("eval.release",),
                    "workflow_ref": "workflow.main",
                }
            )
        )


def test_action_package_cannot_claim_execution() -> None:
    with pytest.raises(ValidationError):
        ActionPackage(
            **(
                META
                | {
                    "id": "action.send-1",
                    "tool_ref": "tool.send",
                    "action_class": ActionClass.external_send,
                    "inputs": {"message": "hello"},
                    "expected_side_effects": ("Sends one message",),
                    "idempotency_key": "send-1",
                    "human_gate_ref": "gate.owner",
                    "executed": True,
                }
            )
        )


def test_rejected_human_gate_decision_requires_unknown_and_run_refs() -> None:
    with pytest.raises(ValidationError, match="unknown_ref"):
        HumanGateDecision(
            **(
                META
                | {
                    "id": "decision.send-1",
                    "action_package_ref": "action.send-1",
                    "decision": HumanGateDecisionKind.reject,
                    "actor_id": "owner",
                    "decided_at": NOW,
                    "recovery_entry": "Return to review",
                    "run_ref": "run.send-1",
                }
            )
        )
