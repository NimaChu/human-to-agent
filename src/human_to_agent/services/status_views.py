from __future__ import annotations

import json
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.assets import WorkspaceManifest
from human_to_agent.domain.readiness import ReadinessAssessment
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex


def assess_stage_view(root: Path, workspace_id: str) -> CommandResult:
    workspace = root / "workspaces" / workspace_id
    manifest_path = workspace / "workspace.yaml"
    if not manifest_path.is_file():
        raise FoundryError("schema", "workspace.missing", f"Workspace is missing: {workspace_id}")
    manifest = WorkspaceManifest.model_validate(yaml.safe_load(manifest_path.read_text()))
    if manifest.current_stage == 5:
        gate_path = workspace / ".foundry" / "release-gate.yaml"
        target = "complete_release"
    else:
        target_stage = manifest.current_stage + 1
        gate_path = workspace / ".foundry" / f"stage-{target_stage}-gate.yaml"
        target = f"stage{target_stage}"
    gate = yaml.safe_load(gate_path.read_text()) if gate_path.is_file() else None
    passed = isinstance(gate, dict) and gate.get("passed") is True
    evidence = gate.get("evidence_refs", []) if isinstance(gate, dict) else []
    diagnostics: list[dict[str, object]] = []
    if not passed:
        diagnostics.append(
            {
                "category": "gate",
                "code": "stage.gap",
                "message": f"{target} is not yet proven by a passing gate artifact.",
                "path": str(gate_path),
            }
        )
    return CommandResult(
        command="stage assess",
        status="ok" if passed else "error",
        exit_code=0 if passed else 5,
        diagnostics=diagnostics,
        next_actions=[f"target={target}", *[f"evidence={item}" for item in evidence]],
    )


def readiness_view(root: Path, workspace_id: str) -> CommandResult:
    path = root / "workspaces" / workspace_id / "LOOP-READINESS" / "assessment.yaml"
    if not path.is_file():
        raise FoundryError("evidence", "readiness.missing", "Readiness assessment is missing.")
    try:
        assessment = ReadinessAssessment.model_validate(yaml.safe_load(path.read_text()))
    except ValueError as error:
        raise FoundryError("schema", "readiness.invalid", str(error)) from error
    return CommandResult(
        command="readiness assess",
        next_actions=[
            f"result={assessment.result.value}",
            f"recommended_ceiling={assessment.recommended_ceiling.value}",
            *assessment.next_actions,
        ],
    )


def diff_view(root: Path, workspace_id: str) -> CommandResult:
    snapshot = SourceRepository(root).snapshot(workspace_id)
    index_path = snapshot.workspace_path / ".foundry" / "artifact-index.yaml"
    if not index_path.is_file():
        raise FoundryError("filesystem", "index.missing", "Artifact index is missing.")
    index = ArtifactIndex.model_validate(yaml.safe_load(index_path.read_text()))
    source = {item.path: item.sha256 for item in snapshot.files}
    recorded = {item.path: item.sha256 for item in index.entries}
    changed = sorted(
        path for path in source.keys() | recorded.keys() if source.get(path) != recorded.get(path)
    )
    distribution = root / "dist" / workspace_id / "release" / "BUILD-MANIFEST.json"
    generated_drift: list[str] = []
    if distribution.is_file():
        manifest = json.loads(distribution.read_text(encoding="utf-8"))
        if manifest.get("source_tree_digest") != tree_digest(snapshot):
            generated_drift.append("generated-output drift: release source digest differs")
    return CommandResult(
        command="diff",
        status="changed" if changed or generated_drift else "ok",
        changed_files=changed,
        next_actions=generated_drift,
    )
