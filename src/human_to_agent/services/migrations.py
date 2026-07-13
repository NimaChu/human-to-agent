from __future__ import annotations

import copy
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from human_to_agent.services.changes import build_artifact_index, render_artifact_index

Transform = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Migration:
    from_version: str
    to_version: str
    transform: Transform


@dataclass(frozen=True, slots=True)
class MigrationResult:
    from_version: str
    to_version: str
    applied: bool
    event_scope: EventScope


class MigrationService:
    def __init__(
        self,
        root: Path,
        event_store: EventStore,
        *,
        validator: Callable[[Path], bool],
    ) -> None:
        self.root = root.resolve()
        self.event_store = event_store
        self.validator = validator

    def migrate(
        self,
        workspace_id: str,
        migrations: tuple[Migration, ...],
        *,
        target_version: str,
        actor: str,
        at: datetime,
        dry_run: bool = False,
    ) -> MigrationResult:
        manager = TransactionManager(self.root, self.event_store)
        return manager.run_locked(
            workspace_id,
            lambda: self._migrate_locked(
                workspace_id,
                migrations,
                target_version=target_version,
                actor=actor,
                at=at,
                dry_run=dry_run,
                manager=manager,
            ),
        )

    def _migrate_locked(
        self,
        workspace_id: str,
        migrations: tuple[Migration, ...],
        *,
        target_version: str,
        actor: str,
        at: datetime,
        dry_run: bool,
        manager: TransactionManager,
    ) -> MigrationResult:
        repository = SourceRepository(self.root)
        source = repository.snapshot(workspace_id)
        workspace = source.workspace_path
        manifest_source = source.by_path().get("workspace.yaml")
        if manifest_source is None:
            raise ValueError("workspace manifest is missing")
        original = manifest_source.source_path.read_bytes()
        index_path = workspace / ".foundry" / "artifact-index.yaml"
        try:
            recorded_index = ArtifactIndex.model_validate(
                yaml.safe_load(index_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, yaml.YAMLError) as error:
            raise ValueError("recorded artifact index is missing or invalid") from error
        if recorded_index != build_artifact_index(source):
            raise ValueError("unrecorded source changes must be resolved before migration")
        raw = yaml.safe_load(original)
        if not isinstance(raw, dict):
            raise ValueError("workspace manifest must be a mapping")
        start = str(raw.get("schema_version"))
        candidate = copy.deepcopy(raw)
        current = start
        by_version = {item.from_version: item for item in migrations}
        while current != target_version:
            migration = by_version.get(current)
            if migration is None:
                raise ValueError(f"no migration from Schema version {current}")
            input_value = copy.deepcopy(candidate)
            input_before = copy.deepcopy(input_value)
            candidate = migration.transform(input_value)
            if input_value != input_before:
                raise ValueError("migration mutated its input")
            if str(candidate.get("schema_version")) != migration.to_version:
                raise ValueError("migration did not set its declared target Schema version")
            current = migration.to_version
        scope = EventScope(
            scope_id=workspace_id,
            log_path=workspace / ".foundry" / "events.jsonl",
        )
        result = MigrationResult(start, current, False, scope)
        rendered = yaml.safe_dump(candidate, sort_keys=False, allow_unicode=True).encode()
        with tempfile.TemporaryDirectory(prefix="hta-migration-") as temporary:
            candidate_repository = Path(temporary)
            candidate_workspace = candidate_repository / "workspaces" / workspace_id
            candidate_workspace.mkdir(parents=True)
            for item in source.files:
                target = candidate_workspace.joinpath(*item.path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(item.canonical_content)
            (candidate_workspace / "workspace.yaml").write_bytes(rendered)
            candidate_source = SourceRepository(candidate_repository).snapshot(workspace_id)
            candidate_index = build_artifact_index(candidate_source)
            candidate_index_bytes = render_artifact_index(candidate_index)
            candidate_index_path = candidate_workspace / ".foundry/artifact-index.yaml"
            candidate_index_path.parent.mkdir(parents=True)
            candidate_index_path.write_bytes(candidate_index_bytes)
            if not self.validator(candidate_workspace):
                return result
            after_digest = tree_digest(candidate_source)
        if dry_run:
            return result
        plan = MutationPlan(
            transaction_id=f"migration-{workspace_id}-{start}-{current}",
            workspace_id=workspace_id,
            event_scope=scope,
            mutations=(
                FileMutation("workspace.yaml", rendered),
                FileMutation(".foundry/artifact-index.yaml", candidate_index_bytes),
            ),
            index_relative_path=".foundry/artifact-index.yaml",
        )
        event = EventDraft(
            event_id=f"migration-{workspace_id}-{start}-{current}",
            workspace_id=workspace_id,
            at=at,
            actor=actor,
            command="migrate",
            asset_refs=(f"workspace.{workspace_id}",),
            before_digest=tree_digest(source),
            after_digest=after_digest,
            result="committed",
            payload={"from_version": start, "to_version": current},
        )
        manager._commit_locked(plan, event)
        return MigrationResult(start, current, True, scope)


def migration_status(
    root: Path, workspace_id: str, target_version: str, *, dry_run: bool
) -> CommandResult:
    try:
        source = SourceRepository(root).snapshot(workspace_id).by_path().get("workspace.yaml")
    except FileNotFoundError as error:
        raise FoundryError(
            "schema", "workspace.missing", f"Workspace is missing: {workspace_id}"
        ) from error
    except (OSError, ValueError) as error:
        raise FoundryError(
            "filesystem",
            "migration.path_unsafe",
            "Migration cannot read an unsafe workspace path.",
        ) from error
    if source is None:
        raise FoundryError("schema", "workspace.missing", f"Workspace is missing: {workspace_id}")
    raw = yaml.safe_load(source.canonical_content)
    current = str(raw.get("schema_version")) if isinstance(raw, dict) else "invalid"
    if current != target_version:
        raise FoundryError(
            "migration",
            "migration.path_missing",
            f"No registered migration path from {current} to {target_version}.",
        )
    return CommandResult(
        command="migrate",
        status="dry-run" if dry_run else "ok",
        next_actions=[f"schema_version={current}", "No migration required."],
    )
