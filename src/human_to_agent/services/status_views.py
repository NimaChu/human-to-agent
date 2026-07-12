from __future__ import annotations

import json
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.readiness import ReadinessAssessment
from human_to_agent.domain.stages import (
    GateStatus,
    Stage,
    assess_complete_release,
    assess_stage,
)
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.assessment_state import load_assessment_state


def assess_stage_view(root: Path, workspace_id: str) -> CommandResult:
    state = load_assessment_state(root, workspace_id)
    if state.manifest.current_stage == 5:
        report = assess_complete_release(state.assessment)
    else:
        report = assess_stage(Stage(state.manifest.current_stage + 1), state.assessment)
    diagnostics: list[dict[str, object]] = [
        {
            "category": "gate",
            "code": "stage.gap",
            "message": check.message,
            "path": "ASSESSMENTS/stage-state.yaml",
            **({"asset_id": check.fact.value} if check.fact is not None else {}),
        }
        for check in report.checks
        if check.status is not GateStatus.satisfied
    ]
    evidence = sorted(
        {
            reference
            for check in report.checks
            for reference in check.evidence_refs
        }
    )
    next_actions = [
        action
        for check in report.checks
        if check.status is not GateStatus.satisfied
        if (action := check.next_action) is not None
    ]
    return CommandResult(
        command="stage assess",
        status="ok" if report.passed else "error",
        exit_code=0 if report.passed else 5,
        diagnostics=diagnostics,
        next_actions=[
            f"target={report.target}",
            *[f"evidence={item}" for item in evidence],
            *next_actions,
        ],
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
