from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.assets import WorkspaceManifest
from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.canonical import canonical_bytes
from harness_foundry.repositories.events import EventStore
from harness_foundry.repositories.index import ArtifactIndex
from harness_foundry.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from harness_foundry.services.changes import render_artifact_index


def advance_stage(root: Path, workspace_id: str, *, actor: str, dry_run: bool) -> CommandResult:
    workspace = root / "workspaces" / workspace_id
    manifest_path = workspace / "workspace.yaml"
    if not manifest_path.is_file():
        raise FoundryError("schema", "workspace.missing", f"Workspace is missing: {workspace_id}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = WorkspaceManifest.model_validate(raw)
    if manifest.current_stage >= 5:
        return CommandResult(command="stage advance", next_actions=["Already at stage 5."])
    target = manifest.current_stage + 1
    gate_path = workspace / ".foundry" / f"stage-{target}-gate.yaml"
    gate = yaml.safe_load(gate_path.read_text(encoding="utf-8")) if gate_path.is_file() else None
    if (
        not isinstance(gate, dict)
        or gate.get("passed") is not True
        or not gate.get("evidence_refs")
    ):
        raise FoundryError(
            "gate", "stage.gate_failed", f"Stage {target} gate lacks direct evidence."
        )
    now = datetime.now(UTC)
    updated = manifest.model_copy(
        update={
            "current_stage": target,
            "revision": manifest.revision + 1,
            "updated_at": now,
        }
    )
    manifest_bytes = yaml.safe_dump(
        updated.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    index_path = workspace / ".foundry" / "artifact-index.yaml"
    index = ArtifactIndex.model_validate(yaml.safe_load(index_path.read_text(encoding="utf-8")))
    entries = tuple(
        entry.model_copy(
            update={
                "revision": updated.revision,
                "sha256": hashlib.sha256(
                    canonical_bytes(updated.model_dump(mode="json"))
                ).hexdigest(),
            }
        )
        if entry.path == "workspace.yaml"
        else entry
        for entry in index.entries
    )
    index_bytes = render_artifact_index(index.model_copy(update={"entries": entries}))
    if dry_run:
        return CommandResult(command="stage advance", status="dry-run")
    scope = EventScope(scope_id=workspace_id, log_path=workspace / ".foundry" / "events.jsonl")
    event = EventDraft(
        event_id=f"stage-{workspace_id}-{target}-{updated.revision}",
        workspace_id=workspace_id,
        at=now,
        actor=actor,
        command="stage advance",
        asset_refs=(manifest.id,),
        before_digest=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        after_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        result="committed",
        payload={"from_stage": manifest.current_stage, "to_stage": target},
    )
    plan = MutationPlan(
        transaction_id=event.event_id,
        workspace_id=workspace_id,
        event_scope=scope,
        mutations=(
            FileMutation("workspace.yaml", manifest_bytes),
            FileMutation(".foundry/artifact-index.yaml", index_bytes),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )
    TransactionManager(root, EventStore()).commit(plan, event)
    return CommandResult(
        command="stage advance",
        changed_files=[str(manifest_path), str(index_path)],
        next_actions=[f"advanced_to={target}"],
    )


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
    workspace = root / "workspaces" / workspace_id
    manifest_path = workspace / "workspace.yaml"
    if not manifest_path.is_file():
        raise FoundryError("schema", "workspace.missing", f"Workspace is missing: {workspace_id}")
    manifest = WorkspaceManifest.model_validate(yaml.safe_load(manifest_path.read_text()))
    if target < 1 or target >= manifest.current_stage:
        raise FoundryError(
            "usage", "stage.reopen_target", "Reopen target must be below current stage."
        )
    if not evidence_ref.strip() or not reason.strip():
        raise FoundryError(
            "evidence", "stage.reopen_evidence", "Reopen evidence and reason are required."
        )
    now = datetime.now(UTC)
    updated = manifest.model_copy(
        update={"current_stage": target, "revision": manifest.revision + 1, "updated_at": now}
    )
    manifest_bytes = yaml.safe_dump(
        updated.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    index_path = workspace / ".foundry" / "artifact-index.yaml"
    index = ArtifactIndex.model_validate(yaml.safe_load(index_path.read_text(encoding="utf-8")))
    entries = tuple(
        entry.model_copy(
            update={
                "revision": updated.revision,
                "sha256": hashlib.sha256(
                    canonical_bytes(updated.model_dump(mode="json"))
                ).hexdigest(),
            }
        )
        if entry.path == "workspace.yaml"
        else entry
        for entry in index.entries
    )
    index_bytes = render_artifact_index(index.model_copy(update={"entries": entries}))
    if dry_run:
        return CommandResult(command="stage reopen", status="dry-run")
    scope = EventScope(scope_id=workspace_id, log_path=workspace / ".foundry" / "events.jsonl")
    event = EventDraft(
        event_id=f"stage-reopen-{workspace_id}-{target}-{updated.revision}",
        workspace_id=workspace_id,
        at=now,
        actor=actor,
        command="stage reopen",
        asset_refs=(manifest.id,),
        before_digest=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        after_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        result="committed",
        payload={
            "from_stage": manifest.current_stage,
            "to_stage": target,
            "reason": reason,
            "evidence_ref": evidence_ref,
        },
    )
    plan = MutationPlan(
        transaction_id=event.event_id,
        workspace_id=workspace_id,
        event_scope=scope,
        mutations=(
            FileMutation("workspace.yaml", manifest_bytes),
            FileMutation(".foundry/artifact-index.yaml", index_bytes),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )
    TransactionManager(root, EventStore()).commit(plan, event)
    return CommandResult(
        command="stage reopen",
        changed_files=[str(manifest_path), str(index_path)],
        next_actions=[f"reopened_to={target}"],
    )
