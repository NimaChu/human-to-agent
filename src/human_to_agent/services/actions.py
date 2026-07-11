from __future__ import annotations

import hashlib
from datetime import datetime

from human_to_agent.domain.assets import (
    ActionClass,
    ActionPackage,
    HumanGateDecision,
    HumanGateDecisionKind,
    ToolSpec,
)
from human_to_agent.repositories.canonical import canonical_bytes


class HumanActionService:
    def prepare(
        self,
        tool: ToolSpec,
        *,
        workspace_id: str,
        run_ref: str,
        inputs: dict[str, object],
        actor: str,
        at: datetime,
    ) -> ActionPackage:
        if tool.action_class is ActionClass.forbidden:
            raise ValueError("forbidden actions cannot be prepared")
        if (
            tool.action_class in {ActionClass.external_send, ActionClass.irreversible}
            and not tool.human_gate_ref
        ):
            raise ValueError("external or irreversible action requires a Human Gate")
        digest = hashlib.sha256(canonical_bytes(inputs)).hexdigest()
        return ActionPackage(
            schema_version="1",
            id=f"action.{digest[:16]}",
            workspace_id=workspace_id,
            revision=1,
            status="prepared",
            owners=(actor,),
            created_at=at,
            updated_at=at,
            provenance=f"prepared from {run_ref}",
            links=(run_ref,),
            evidence_refs=(),
            tool_ref=tool.id,
            action_class=tool.action_class,
            inputs=inputs,
            expected_side_effects=tool.side_effects,
            idempotency_key=digest,
            human_gate_ref=tool.human_gate_ref or "gate.not-required",
            executed=False,
        )

    def decide(
        self,
        package: ActionPackage,
        decision: HumanGateDecisionKind,
        *,
        actor: str,
        run_ref: str,
        at: datetime,
        unknown_ref: str | None = None,
        modified_action_ref: str | None = None,
    ) -> HumanGateDecision:
        return HumanGateDecision(
            schema_version="1",
            id=f"decision.{package.id}.{decision.value}",
            workspace_id=package.workspace_id,
            revision=1,
            status="recorded",
            owners=(actor,),
            created_at=at,
            updated_at=at,
            provenance="human gate decision",
            links=(package.id, run_ref),
            evidence_refs=(),
            action_package_ref=package.id,
            decision=decision,
            actor_id=actor,
            decided_at=at,
            recovery_entry="Package remains unexecuted; review or discard it.",
            run_ref=run_ref,
            unknown_ref=unknown_ref,
            modified_action_ref=modified_action_ref,
        )

    @staticmethod
    def requires_revalidation(decision: HumanGateDecision) -> bool:
        return decision.decision is HumanGateDecisionKind.modify
