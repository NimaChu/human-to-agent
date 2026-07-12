from __future__ import annotations

from collections.abc import Mapping

import yaml
from pydantic import BaseModel, ValidationError

from human_to_agent.domain.assessment import AssessmentSnapshot
from human_to_agent.domain.assets import WorkspaceManifest
from human_to_agent.domain.readiness import ReadinessAssessment
from human_to_agent.domain.references import ReferenceGraph, validate_references
from human_to_agent.repositories.filesystem import SourceSnapshot
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.validators.report import Diagnostic, ValidationReport


def infer_schema_name(path: str) -> str | None:
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
    identifiers: dict[str, BaseModel] = {}
    assessment: AssessmentSnapshot | None = None
    manifest: WorkspaceManifest | None = None
    readiness_assessments: list[ReadinessAssessment] = []
    for source in snapshot.files:
        if source.path.startswith("EVIDENCE/sources/"):
            continue
        if not source.path.endswith((".yaml", ".yml")):
            continue
        schema_name = infer_schema_name(source.path)
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
                if asset_id in identifiers:
                    diagnostics.append(
                        Diagnostic(
                            category="schema",
                            code="asset.id_duplicate",
                            message=f"Duplicate asset ID: {asset_id}",
                            path=source.path,
                            asset_id=asset_id,
                        )
                    )
                assets[asset_id] = asset
                identifiers[asset_id] = asset
            assessment_id = getattr(asset, "assessment_id", None)
            if isinstance(assessment_id, str):
                if assessment_id in identifiers:
                    diagnostics.append(
                        Diagnostic(
                            category="schema",
                            code="asset.id_duplicate",
                            message=f"Duplicate assessment ID: {assessment_id}",
                            path=source.path,
                            asset_id=assessment_id,
                        )
                    )
                identifiers[assessment_id] = asset
            if isinstance(asset, AssessmentSnapshot):
                assessment = asset
            elif isinstance(asset, WorkspaceManifest):
                manifest = asset
            elif isinstance(asset, ReadinessAssessment):
                readiness_assessments.append(asset)
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
    reference_report = validate_references(graph, known_ids=set(identifiers))
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

    def validate_direct_refs(source_id: str, refs: set[str]) -> None:
        for target_id in sorted(refs):
            target = identifiers.get(target_id)
            if target is None:
                diagnostics.append(
                    Diagnostic(
                        category="reference",
                        code="reference.missing",
                        message=f"{source_id} references missing {target_id}",
                        asset_id=source_id,
                        target_id=target_id,
                    )
                )
            elif str(getattr(target, "status", "")).lower() == "draft":
                diagnostics.append(
                    Diagnostic(
                        category="evidence",
                        code="evidence.draft",
                        message=f"{source_id} references draft evidence {target_id}",
                        asset_id=source_id,
                        target_id=target_id,
                    )
                )

    if assessment is not None:
        if manifest is not None and assessment.workspace_id != manifest.workspace_id:
            diagnostics.append(
                Diagnostic(
                    category="schema",
                    code="assessment.workspace_mismatch",
                    message="Assessment workspace_id does not match workspace.yaml.",
                    path="ASSESSMENTS/stage-state.yaml",
                )
            )
        if manifest is not None and assessment.current_stage != manifest.current_stage:
            diagnostics.append(
                Diagnostic(
                    category="schema",
                    code="assessment.stage_mismatch",
                    message="Assessment current_stage does not match workspace.yaml.",
                    path="ASSESSMENTS/stage-state.yaml",
                )
            )
        assessment_refs = {
            ref for refs in assessment.evidence.values() for ref in refs
        } | set(assessment.case_evaluation_refs) | set(assessment.readiness_evidence_refs)
        validate_direct_refs("assessment.stage-state", assessment_refs)

    for readiness in readiness_assessments:
        readiness_refs = {
            ref
            for dimension in readiness.dimensions.values()
            for ref in dimension.evidence_refs
        }
        validate_direct_refs(readiness.assessment_id, readiness_refs)

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
