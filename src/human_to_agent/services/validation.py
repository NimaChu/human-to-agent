from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.services.workspaces import (
    _assert_safe_workspace_tree,
    _is_link_or_junction,
    _safe_workspace_root,
    _validate_workspace_component,
)
from human_to_agent.validators.workspace import validate_workspace


def validate_root(root: Path, workspace: str | None) -> CommandResult:
    if not (root / "human-to-agent.yaml").is_file():
        return CommandResult(
            command="validate",
            status="error",
            exit_code=3,
            diagnostics=[
                {
                    "category": "schema",
                    "code": "schema.root_missing",
                    "message": "human-to-agent.yaml is missing",
                    "path": str(root / "human-to-agent.yaml"),
                }
            ],
        )
    diagnostics: list[dict[str, object]] = []
    try:
        workspace_root = _safe_workspace_root(root)
        repository = SourceRepository(root)
    except (FoundryError, OSError, ValueError) as error:
        code = error.code if isinstance(error, FoundryError) else "filesystem.unsafe_workspace_root"
        message = error.message if isinstance(error, FoundryError) else str(error)
        diagnostics.append(
            {
                "category": "filesystem",
                "code": code,
                "message": message,
                "path": "workspaces",
            }
        )
        return _validation_result(diagnostics)

    if workspace is not None:
        try:
            _validate_workspace_component(workspace)
            workspace_path = workspace_root / workspace
            if _is_link_or_junction(workspace_path):
                raise FoundryError(
                    "filesystem",
                    "filesystem.unsafe_workspace_path",
                    "Workspace path cannot be a symlink or junction.",
                )
        except FoundryError as error:
            diagnostics.append(
                {
                    "category": "filesystem",
                    "code": error.code,
                    "message": error.message,
                    "path": f"workspaces/{workspace}",
                }
            )
            return _validation_result(diagnostics)
        slugs = [workspace]
    else:
        slugs = []
        if workspace_root.exists():
            for path in sorted(workspace_root.iterdir()):
                if path.name.startswith("."):
                    continue
                if _is_link_or_junction(path):
                    diagnostics.append(
                        {
                            "category": "filesystem",
                            "code": "filesystem.unsafe_workspace_path",
                            "message": "Workspace path cannot be a symlink or junction.",
                            "path": f"workspaces/{path.name}",
                        }
                    )
                elif path.is_dir():
                    slugs.append(path.name)

    for slug in slugs:
        workspace_path = workspace_root / slug
        try:
            if workspace_path.is_dir():
                _assert_safe_workspace_tree(workspace_path)
        except FoundryError as error:
            diagnostics.append(
                {
                    "category": "filesystem",
                    "code": error.code,
                    "message": error.message,
                    "path": f"workspaces/{slug}",
                }
            )
            continue
        try:
            snapshot = repository.snapshot(slug)
            index_path = snapshot.workspace_path / ".foundry" / "artifact-index.yaml"
            index = None
            if index_path.is_file():
                index = ArtifactIndex.model_validate(
                    yaml.safe_load(index_path.read_text(encoding="utf-8"))
                )
            report = validate_workspace(snapshot, DEFAULT_MODELS, recorded_index=index)
            diagnostics.extend(
                item.model_dump(mode="json", exclude_none=True) for item in report.diagnostics
            )
        except (FileNotFoundError, ValidationError, ValueError, yaml.YAMLError) as error:
            diagnostics.append(
                {"category": "schema", "code": "schema.invalid", "message": str(error)}
            )
    return _validation_result(diagnostics)


def _validation_result(diagnostics: list[dict[str, object]]) -> CommandResult:
    category_exit = {"schema": 3, "reference": 4, "evidence": 5, "filesystem": 8}
    exit_code = max(
        (category_exit.get(str(item["category"]), 3) for item in diagnostics), default=0
    )
    return CommandResult(
        command="validate",
        status="ok" if not diagnostics else "error",
        exit_code=exit_code,
        diagnostics=diagnostics,
    )
