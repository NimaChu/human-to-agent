from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.stages import Stage, assess_stage, decide_stage_transition
from human_to_agent.services.assessment_state import load_assessment_state
from human_to_agent.services.asset_writer import write_assets


def _yaml_bytes(model: BaseModel) -> bytes:
    return yaml.safe_dump(
        model.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()


def _transition_result(result: CommandResult, action: str) -> CommandResult:
    return CommandResult(
        command=result.command,
        status=result.status,
        exit_code=result.exit_code,
        diagnostics=result.diagnostics,
        changed_files=result.changed_files,
        next_actions=[*result.next_actions, action],
    )


def advance_stage(root: Path, workspace_id: str, *, actor: str, dry_run: bool) -> CommandResult:
    state = load_assessment_state(root, workspace_id, require_recorded=True)
    manifest = state.manifest
    if manifest.current_stage >= Stage.stage5:
        return CommandResult(command="stage advance", next_actions=["Already at stage 5."])
    current = Stage(manifest.current_stage)
    target = Stage(manifest.current_stage + 1)
    report = assess_stage(target, state.assessment)
    if not report.passed:
        gaps = "; ".join(check.message for check in report.checks if check.next_action)
        raise FoundryError("gate", "stage.gate_failed", gaps or f"{target.name} gate did not pass.")
    now = datetime.now(UTC)
    decide_stage_transition(
        current,
        target,
        report,
        actor=actor,
        at=now,
        reason=f"Computed {target.name} gate passed.",
    )
    updated_manifest = manifest.model_copy(
        update={
            "current_stage": int(target),
            "revision": manifest.revision + 1,
            "updated_at": now,
        }
    )
    updated_assessment = state.assessment.model_copy(update={"current_stage": int(target)})
    evidence_refs = tuple(
        sorted({reference for check in report.checks for reference in check.evidence_refs})
    )
    result = write_assets(
        root,
        workspace_id,
        (
            ("workspace.yaml", _yaml_bytes(updated_manifest)),
            ("ASSESSMENTS/stage-state.yaml", _yaml_bytes(updated_assessment)),
        ),
        command="stage advance",
        asset_ids=(manifest.id, *evidence_refs),
        actor=actor,
        dry_run=dry_run,
        event_payload={"from_stage": int(current), "to_stage": int(target)},
    )
    return _transition_result(result, f"advanced_to={int(target)}")


def reopen_stage(
    root: Path,
    workspace_id: str,
    *,
    target: int,
    evidence_ref: str,
    reason: str,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    state = load_assessment_state(root, workspace_id, require_recorded=True)
    manifest = state.manifest
    if target < 1 or target >= manifest.current_stage:
        raise FoundryError(
            "usage", "stage.reopen_target", "Reopen target must be below current stage."
        )
    evidence_ref = evidence_ref.strip()
    reason = reason.strip()
    if not evidence_ref or not reason:
        raise FoundryError(
            "evidence", "stage.reopen_evidence", "Reopen evidence and reason are required."
        )
    state.require_reference(evidence_ref)
    now = datetime.now(UTC)
    updated_manifest = manifest.model_copy(
        update={
            "current_stage": target,
            "revision": manifest.revision + 1,
            "updated_at": now,
        }
    )
    updated_assessment = state.assessment.model_copy(update={"current_stage": target})
    result = write_assets(
        root,
        workspace_id,
        (
            ("workspace.yaml", _yaml_bytes(updated_manifest)),
            ("ASSESSMENTS/stage-state.yaml", _yaml_bytes(updated_assessment)),
        ),
        command="stage reopen",
        asset_ids=(manifest.id, evidence_ref),
        actor=actor,
        dry_run=dry_run,
        event_payload={
            "from_stage": manifest.current_stage,
            "to_stage": target,
            "reason": reason,
            "evidence_ref": evidence_ref,
        },
    )
    return _transition_result(result, f"reopened_to={target}")
