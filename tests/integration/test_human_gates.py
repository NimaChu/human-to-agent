from datetime import UTC, datetime

from harness_foundry.domain.assets import (
    ActionClass,
    HumanGateDecisionKind,
    ToolSpec,
)
from harness_foundry.services.actions import HumanActionService

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def tool(action_class: ActionClass = ActionClass.external_send) -> ToolSpec:
    return ToolSpec.model_validate(
        {
            "schema_version": "1",
            "id": "tool.mail",
            "workspace_id": "pilot",
            "revision": 1,
            "status": "validated",
            "owners": ["owner"],
            "created_at": NOW,
            "updated_at": NOW,
            "provenance": "test",
            "links": [],
            "evidence_refs": [],
            "name": "mail",
            "input_schema_ref": "schema.mail-input",
            "output_schema_ref": "schema.mail-output",
            "action_class": action_class,
            "required_permissions": ["mail.prepare"],
            "side_effects": ["message may be sent after a separate executor"],
            "idempotent": False,
            "retry_semantics": "never retry without review",
            "executable_adapter": None if action_class is ActionClass.forbidden else "mail-adapter",
            "human_gate_ref": "gate.mail"
            if action_class in {ActionClass.external_send, ActionClass.irreversible}
            else None,
        }
    )


def test_release_prepares_package_but_never_executes_external_action() -> None:
    package = HumanActionService().prepare(
        tool(),
        workspace_id="pilot",
        run_ref="run.1",
        inputs={"recipient": "owner@example.invalid"},
        actor="agent",
        at=NOW,
    )
    assert package.executed is False
    decision = HumanActionService().decide(
        package,
        HumanGateDecisionKind.approve,
        actor="owner",
        run_ref="run.1",
        at=NOW,
    )
    assert package.executed is False
    assert decision.recovery_entry


def test_rejection_links_unknown_and_modification_requires_revalidation() -> None:
    service = HumanActionService()
    package = service.prepare(
        tool(), workspace_id="pilot", run_ref="run.1", inputs={"x": 1}, actor="agent", at=NOW
    )
    rejection = service.decide(
        package,
        HumanGateDecisionKind.reject,
        actor="owner",
        run_ref="run.1",
        at=NOW,
        unknown_ref="unknown.rejected-action",
    )
    assert rejection.unknown_ref == "unknown.rejected-action"
    modified = service.decide(
        package,
        HumanGateDecisionKind.modify,
        actor="owner",
        run_ref="run.1",
        at=NOW,
        modified_action_ref="action.revised",
    )
    assert modified.modified_action_ref == "action.revised"
    assert service.requires_revalidation(modified)


def test_forbidden_actions_cannot_be_prepared() -> None:
    service = HumanActionService()
    try:
        service.prepare(
            tool(ActionClass.forbidden),
            workspace_id="pilot",
            run_ref="run.1",
            inputs={"x": 1},
            actor="agent",
            at=NOW,
        )
    except ValueError as error:
        assert "forbidden" in str(error)
    else:
        raise AssertionError("forbidden action was prepared")
