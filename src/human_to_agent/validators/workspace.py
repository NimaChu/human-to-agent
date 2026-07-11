from __future__ import annotations

from collections.abc import Mapping

import yaml
from pydantic import BaseModel, ValidationError

from human_to_agent.domain.references import ReferenceGraph, validate_references
from human_to_agent.repositories.filesystem import SourceSnapshot
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.validators.report import Diagnostic, ValidationReport


def _infer_schema_name(path: str) -> str | None:
    if path == "workspace.yaml":
        return "workspace"
    parts = path.split("/")
    roots = {
        "TASK-CONTRACT": "task-contract",
        "SKILLS": "skill",
        "CASES": "case",
        "EVALS": "evaluation",
        "WORKFLOW": "workflow",
        "TOOLS": "tool",
        "CONTEXT": "context",
        "STATE": "state-model",
        "POLICIES": "policy",
        "HUMAN-GATES": "human-gate",
        "EXCEPTIONS": "exception",
        "UNKNOWNS": "unknown",
        "EVALUATORS": "evaluator",
        "LOOP-READINESS": "readiness-assessment",
        "RUNS": "run",
        "HARNESS": "harness",
        "EVIDENCE": "evidence",
        "ASSESSMENTS": "stage-state",
    }
    return roots.get(parts[0]) if parts else None


def validate_workspace(
    snapshot: SourceSnapshot,
    model_catalog: Mapping[str, type[BaseModel]],
    *,
    recorded_index: ArtifactIndex | None = None,
) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    assets: dict[str, BaseModel] = {}
    for source in snapshot.files:
        if not source.path.endswith((".yaml", ".yml")):
            continue
        schema_name = _infer_schema_name(source.path)
        if schema_name is None or schema_name not in model_catalog:
            diagnostics.append(
                Diagnostic(
                    category="schema",
                    code="schema.unrecognized",
                    message="No registered asset Schema matches this path.",
                    path=source.path,
                )
            )
            continue
        try:
            raw = yaml.safe_load(source.source_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("asset root must be a mapping")
            asset = model_catalog[schema_name].model_validate(raw)
            asset_id = getattr(asset, "id", None)
            if isinstance(asset_id, str):
                assets[asset_id] = asset
        except (ValidationError, ValueError, yaml.YAMLError) as error:
            diagnostics.append(
                Diagnostic(
                    category="schema",
                    code="schema.invalid",
                    message=str(error),
                    path=source.path,
                )
            )

    graph = ReferenceGraph.from_assets(assets)
    reference_report = validate_references(graph, known_ids=set(assets))
    diagnostics.extend(
        Diagnostic(
            category="reference",
            code=item.code,
            message=item.message,
            asset_id=item.source_id,
            target_id=item.target_id,
        )
        for item in reference_report.errors
    )

    if recorded_index is not None:
        recorded = recorded_index.by_path()
        for source in snapshot.files:
            entry = recorded.get(source.path)
            if entry is None or entry.sha256 != source.sha256:
                diagnostics.append(
                    Diagnostic(
                        category="filesystem",
                        code="source.unrecorded",
                        message="Source content differs from the recorded artifact index.",
                        path=source.path,
                    )
                )

    return ValidationReport(diagnostics=tuple(diagnostics))
