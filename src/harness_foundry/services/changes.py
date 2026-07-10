from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.events import EventStore
from harness_foundry.repositories.filesystem import SourceRepository, SourceSnapshot, tree_digest
from harness_foundry.repositories.index import ArtifactIndex, ArtifactIndexEntry
from harness_foundry.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from harness_foundry.services.schema_catalog import DEFAULT_MODELS
from harness_foundry.validators.workspace import validate_workspace


def build_artifact_index(snapshot: SourceSnapshot) -> ArtifactIndex:
    entries: list[ArtifactIndexEntry] = []
    for source in snapshot.files:
        asset_id = f"file.{source.path.replace('/', '.').lower()}"
        revision = 1
        schema_version = "1"
        if source.path.endswith((".yaml", ".yml")):
            raw = yaml.safe_load(source.source_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
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
    TransactionManager(root, EventStore()).commit(plan, event)
    return CommandResult(command="record-change", changed_files=[str(index_path)])
