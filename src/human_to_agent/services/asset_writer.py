from __future__ import annotations

import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.filesystem import SourceRepository, SourceSnapshot, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.repositories.transactions import FileMutation, MutationPlan, TransactionManager
from human_to_agent.services.changes import build_artifact_index, render_artifact_index
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.validators.workspace import validate_workspace


def _validated_files(
    files: Sequence[tuple[str, bytes]],
) -> tuple[tuple[PurePosixPath, bytes], ...]:
    if not files:
        raise FoundryError(
            "filesystem", "asset.files_empty", "At least one asset file is required."
        )
    validated: list[tuple[PurePosixPath, bytes]] = []
    seen: set[str] = set()
    for relative_path, content in files:
        relative = PurePosixPath(relative_path)
        invalid = (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] == ".foundry"
            or "\\" in relative_path
            or any(":" in part for part in relative.parts)
        )
        if invalid:
            raise FoundryError(
                "filesystem", "asset.path_invalid", "Asset path is not normative and relative."
            )
        normalized = relative.as_posix()
        if normalized in seen:
            raise FoundryError(
                "filesystem", "asset.path_duplicate", f"Asset path is repeated: {normalized}"
            )
        seen.add(normalized)
        validated.append((relative, content))
    return tuple(validated)


def _reject_unrecorded_changes(
    current: SourceSnapshot,
) -> None:
    index_path = current.workspace_path / ".foundry" / "artifact-index.yaml"
    try:
        recorded = ArtifactIndex.model_validate(
            yaml.safe_load(index_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise FoundryError(
            "filesystem",
            "asset.unrecorded_changes",
            "The recorded artifact index is missing or invalid; record or repair it first.",
        ) from error
    expected = build_artifact_index(current)
    if recorded == expected:
        return
    recorded_by_path = recorded.by_path()
    if len(recorded_by_path) != len(recorded.entries):
        raise FoundryError(
            "filesystem",
            "asset.unrecorded_changes",
            "The recorded artifact index contains duplicate paths.",
        )
    current_by_path = current.by_path()
    changed = sorted(
        path
        for path in set(current_by_path) | set(recorded_by_path)
        if (
            path not in current_by_path
            or path not in recorded_by_path
            or current_by_path[path].sha256 != recorded_by_path[path].sha256
        )
    )
    preview = ", ".join(changed[:3]) if changed else "artifact-index metadata"
    raise FoundryError(
        "filesystem",
        "asset.unrecorded_changes",
        f"Unrelated unrecorded changes must be resolved first: {preview}",
    )


def write_assets(
    root: Path,
    workspace_id: str,
    files: Sequence[tuple[str, bytes]],
    *,
    command: str,
    asset_ids: tuple[str, ...],
    actor: str,
    dry_run: bool,
    event_payload: Mapping[str, object] | None = None,
    expected_source_digest: str | None = None,
) -> CommandResult:
    validated_files = _validated_files(files)
    repository = SourceRepository(root)
    manager = TransactionManager(root, EventStore())

    def prepare_and_write() -> CommandResult:
        try:
            current = repository.snapshot(workspace_id)
        except FileNotFoundError as error:
            raise FoundryError("schema", "workspace.missing", str(error)) from error
        except ValueError as error:
            raise FoundryError("filesystem", "asset.path_unsafe", str(error)) from error
        current_digest = tree_digest(current)
        if expected_source_digest is not None and current_digest != expected_source_digest:
            raise FoundryError(
                "filesystem",
                "asset.stale_source",
                "Workspace source changed after this operation read it; retry from current state.",
            )
        _reject_unrecorded_changes(current)
        with tempfile.TemporaryDirectory(prefix="hta-candidate-") as temporary:
            candidate_root = Path(temporary)
            candidate_workspace = candidate_root / "workspaces" / workspace_id
            candidate_workspace.mkdir(parents=True)
            for source in current.files:
                target = candidate_workspace.joinpath(*PurePosixPath(source.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.canonical_content)
            for relative, content in validated_files:
                target = candidate_workspace.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            candidate = SourceRepository(candidate_root).snapshot(workspace_id)
            report = validate_workspace(candidate, DEFAULT_MODELS)
            if not report.passed:
                first = report.diagnostics[0]
                raise FoundryError(first.category, first.code, first.message)
            index_bytes = render_artifact_index(build_artifact_index(candidate))
            after_digest = tree_digest(candidate)
        changed = tuple(
            (relative, content)
            for relative, content in validated_files
            if not (current.workspace_path.joinpath(*relative.parts)).is_file()
            or (current.workspace_path.joinpath(*relative.parts)).read_bytes() != content
        )
        index_relative = ".foundry/artifact-index.yaml"
        index_path = current.workspace_path / index_relative
        index_changed = not index_path.is_file() or index_path.read_bytes() != index_bytes
        if not changed and not index_changed:
            return CommandResult(
                command=command,
                status="dry-run" if dry_run else "ok",
                next_actions=["Content is already recorded."],
            )
        if dry_run:
            return CommandResult(command=command, status="dry-run")
        now = datetime.now(UTC)
        scope = EventScope(
            scope_id=workspace_id,
            log_path=current.workspace_path / ".foundry" / "events.jsonl",
        )
        relative_paths = [relative.as_posix() for relative, _ in validated_files]
        payload: dict[str, object] = dict(event_payload or {})
        payload["relative_paths"] = relative_paths
        if len(relative_paths) == 1:
            payload["relative_path"] = relative_paths[0]
        event = EventDraft(
            event_id=f"{command.replace(' ', '-')}-{after_digest[:20]}",
            workspace_id=workspace_id,
            at=now,
            actor=actor,
            command=command,
            asset_refs=asset_ids,
            before_digest=current_digest,
            after_digest=after_digest,
            result="committed",
            payload=payload,
        )
        mutations = (
            *(FileMutation(relative.as_posix(), content) for relative, content in changed),
            FileMutation(index_relative, index_bytes),
        )
        plan = MutationPlan(
            transaction_id=event.event_id,
            workspace_id=workspace_id,
            event_scope=scope,
            mutations=mutations,
            index_relative_path=index_relative,
        )
        manager._commit_locked(plan, event)
        return CommandResult(
            command=command,
            changed_files=[
                str(current.workspace_path.joinpath(*relative.parts)) for relative, _ in changed
            ],
        )

    return manager.run_locked(workspace_id, prepare_and_write)


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
    expected_source_digest: str | None = None,
) -> CommandResult:
    return write_assets(
        root,
        workspace_id,
        ((relative_path, content),),
        command=command,
        asset_ids=(asset_id,),
        actor=actor,
        dry_run=dry_run,
        expected_source_digest=expected_source_digest,
    )
