from __future__ import annotations

import copy
import hashlib
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.events import EventStore
from harness_foundry.repositories.transactions import FileMutation, MutationPlan, TransactionManager

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
        self.root = root
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
        workspace = self.root / "workspaces" / workspace_id
        manifest_path = workspace / "workspace.yaml"
        original = manifest_path.read_bytes()
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
        with tempfile.TemporaryDirectory(prefix="hf-migration-") as temporary:
            candidate_root = Path(temporary) / workspace_id
            shutil.copytree(workspace, candidate_root)
            (candidate_root / "workspace.yaml").write_bytes(rendered)
            if not self.validator(candidate_root):
                return result
        if dry_run:
            return result
        index_path = workspace / ".foundry" / "artifact-index.yaml"
        plan = MutationPlan(
            transaction_id=f"migration-{workspace_id}-{start}-{current}",
            workspace_id=workspace_id,
            event_scope=scope,
            mutations=(
                FileMutation("workspace.yaml", rendered),
                FileMutation(".foundry/artifact-index.yaml", index_path.read_bytes()),
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
            before_digest=hashlib.sha256(original).hexdigest(),
            after_digest=hashlib.sha256(rendered).hexdigest(),
            result="committed",
            payload={"from_version": start, "to_version": current},
        )
        TransactionManager(self.root, self.event_store).commit(plan, event)
        return MigrationResult(start, current, True, scope)


def migration_status(
    root: Path, workspace_id: str, target_version: str, *, dry_run: bool
) -> CommandResult:
    path = root / "workspaces" / workspace_id / "workspace.yaml"
    if not path.is_file():
        raise FoundryError("schema", "workspace.missing", f"Workspace is missing: {workspace_id}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
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
