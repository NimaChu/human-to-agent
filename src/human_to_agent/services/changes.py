from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.filesystem import (
    SourceRepository,
    SourceSnapshot,
    is_non_normative_asset_path,
    tree_digest,
)
from human_to_agent.repositories.index import ArtifactIndex, ArtifactIndexEntry
from human_to_agent.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.validators.workspace import validate_workspace


def build_artifact_index(snapshot: SourceSnapshot) -> ArtifactIndex:
    entries: list[ArtifactIndexEntry] = []
    for source in snapshot.files:
        asset_id = f"file.{source.path.replace('/', '.').lower()}"
        revision = 1
        schema_version = "1"
        if (
            source.path.endswith((".yaml", ".yml"))
            and not source.path.startswith("EVIDENCE/sources/")
            and not is_non_normative_asset_path(source.path)
        ):
            raw = yaml.safe_load(source.source_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                if source.path == "LOOP-READINESS/autonomy-approval.yaml":
                    workspace_id = raw.get("workspace_id")
                    level = raw.get("level")
                    if isinstance(workspace_id, str) and isinstance(level, str):
                        asset_id = f"autonomy-approval.{workspace_id}.{level}"
                else:
                    asset_id = str(raw.get("id") or raw.get("assessment_id") or asset_id)
                revision = int(raw.get("revision", 1))
                schema_version = str(raw.get("schema_version", "1"))
        entries.append(
            ArtifactIndexEntry(
                asset_id=asset_id,
                path=source.path,
                revision=revision,
                asset_schema_version=schema_version,
                sha256=source.sha256,
            )
        )
    return ArtifactIndex(schema_version="1", entries=tuple(entries))


def render_artifact_index(index: ArtifactIndex) -> bytes:
    return yaml.safe_dump(
        index.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()


def record_change(
    root: Path,
    workspace_id: str,
    *,
    actor: str = "maintainer",
    dry_run: bool = False,
) -> CommandResult:
    manager = TransactionManager(root, EventStore())
    return manager.run_locked(
        workspace_id,
        lambda: _record_change_locked(
            root,
            workspace_id,
            actor=actor,
            dry_run=dry_run,
            manager=manager,
        ),
    )


def _record_change_locked(
    root: Path,
    workspace_id: str,
    *,
    actor: str,
    dry_run: bool,
    manager: TransactionManager,
) -> CommandResult:
    repository = SourceRepository(root)
    try:
        snapshot = repository.snapshot(workspace_id)
    except FileNotFoundError as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error
    validation = validate_workspace(snapshot, DEFAULT_MODELS)
    if not validation.passed:
        first = validation.diagnostics[0]
        raise FoundryError(first.category, first.code, first.message)
    index_path = snapshot.workspace_path / ".foundry" / "artifact-index.yaml"
    previous = index_path.read_bytes() if index_path.exists() else b""
    rendered = render_artifact_index(build_artifact_index(snapshot))
    if rendered == previous:
        return CommandResult(command="record-change", next_actions=["No unrecorded changes."])
    if dry_run:
        return CommandResult(command="record-change", status="dry-run")
    digest = tree_digest(snapshot)
    event_scope = EventScope(
        scope_id=workspace_id,
        log_path=snapshot.workspace_path / ".foundry" / "events.jsonl",
    )
    event = EventDraft(
        event_id=f"record-change-{digest[:20]}",
        workspace_id=workspace_id,
        at=datetime.now(UTC),
        actor=actor,
        command="record-change",
        asset_refs=(f"workspace.{workspace_id}",),
        before_digest=hashlib.sha256(previous).hexdigest(),
        after_digest=digest,
        result="committed",
        payload={"source_file_count": len(snapshot.files)},
    )
    plan = MutationPlan(
        transaction_id=event.event_id,
        workspace_id=workspace_id,
        event_scope=event_scope,
        mutations=(FileMutation(".foundry/artifact-index.yaml", rendered),),
        index_relative_path=".foundry/artifact-index.yaml",
    )
    manager._commit_locked(plan, event)
    return CommandResult(command="record-change", changed_files=[str(index_path)])
