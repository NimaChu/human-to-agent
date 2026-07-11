from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from human_to_agent.services.changes import build_artifact_index, render_artifact_index
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.validators.workspace import validate_workspace


def write_asset(
    root: Path,
    workspace_id: str,
    relative_path: str,
    content: bytes,
    *,
    command: str,
    asset_id: str,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[0] == ".foundry":
        raise FoundryError(
            "filesystem", "asset.path_invalid", "Asset path is not normative and relative."
        )
    repository = SourceRepository(root)
    current = repository.snapshot(workspace_id)
    with tempfile.TemporaryDirectory(prefix="hta-candidate-") as temporary:
        candidate_root = Path(temporary)
        candidate_workspace = candidate_root / "workspaces" / workspace_id
        shutil.copytree(current.workspace_path, candidate_workspace)
        target = candidate_workspace / Path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        candidate = SourceRepository(candidate_root).snapshot(workspace_id)
        report = validate_workspace(candidate, DEFAULT_MODELS)
        if not report.passed:
            first = report.diagnostics[0]
            raise FoundryError(first.category, first.code, first.message)
        index_bytes = render_artifact_index(build_artifact_index(candidate))
        after_digest = tree_digest(candidate)
    if dry_run:
        return CommandResult(command=command, status="dry-run")
    now = datetime.now(UTC)
    scope = EventScope(
        scope_id=workspace_id,
        log_path=current.workspace_path / ".foundry" / "events.jsonl",
    )
    event = EventDraft(
        event_id=f"{command.replace(' ', '-')}-{after_digest[:20]}",
        workspace_id=workspace_id,
        at=now,
        actor=actor,
        command=command,
        asset_refs=(asset_id,),
        before_digest=tree_digest(current),
        after_digest=after_digest,
        result="committed",
        payload={"relative_path": relative.as_posix()},
    )
    index_relative = ".foundry/artifact-index.yaml"
    plan = MutationPlan(
        transaction_id=event.event_id,
        workspace_id=workspace_id,
        event_scope=scope,
        mutations=(
            FileMutation(relative.as_posix(), content),
            FileMutation(index_relative, index_bytes),
        ),
        index_relative_path=index_relative,
    )
    TransactionManager(root, EventStore()).commit(plan, event)
    return CommandResult(
        command=command,
        changed_files=[str(current.workspace_path / Path(relative_path))],
    )
