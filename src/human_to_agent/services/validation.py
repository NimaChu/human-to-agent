from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from human_to_agent.cli.result import CommandResult
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
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
    repository = SourceRepository(root)
    workspace_root = root / "workspaces"
    slugs = (
        [workspace]
        if workspace
        else sorted(path.name for path in workspace_root.iterdir() if path.is_dir())
    )
    diagnostics: list[dict[str, object]] = []
    for slug in slugs:
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
