from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath

import yaml
from pydantic import BaseModel, ValidationError

from human_to_agent.domain.assessment import AssessmentSnapshot
from human_to_agent.domain.assets import WorkspaceManifest
from human_to_agent.domain.evidence import Evidence
from human_to_agent.domain.readiness import AutonomyApproval, AutonomyLevel, ReadinessAssessment
from human_to_agent.domain.references import ReferenceGraph, validate_references
from human_to_agent.domain.unknowns import Unknown
from human_to_agent.repositories.filesystem import SourceSnapshot
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.validators.report import Diagnostic, ValidationReport


def infer_schema_name(path: str) -> str | None:
    if path == "workspace.yaml":
        return "workspace"
    if path == "LOOP-READINESS/autonomy-approval.yaml":
        return "autonomy-approval"
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
    autonomy_approvals: list[AutonomyApproval] = []
    evidence_assets: list[Evidence] = []
    located_assets: list[tuple[str, BaseModel]] = []
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
            located_assets.append((source.path, asset))
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
            if isinstance(assessment_id, str) and not isinstance(asset, AutonomyApproval):
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
            elif isinstance(asset, AutonomyApproval):
                autonomy_approvals.append(asset)
            if isinstance(asset, Evidence):
                evidence_assets.append(asset)
        except (ValidationError, ValueError, yaml.YAMLError) as error:
            diagnostics.append(
                Diagnostic(
                    category="schema",
                    code="schema.invalid",
                    message=str(error),
                    path=source.path,
                )
            )

    if manifest is not None:
        for path, asset in located_assets:
            asset_workspace_id = getattr(asset, "workspace_id", None)
            if (
                isinstance(asset_workspace_id, str)
                and asset_workspace_id != manifest.workspace_id
                and not isinstance(asset, AssessmentSnapshot)
            ):
                diagnostics.append(
                    Diagnostic(
                        category="schema",
                        code="asset.workspace_mismatch",
                        message="Asset workspace_id does not match workspace.yaml.",
                        path=path,
                        asset_id=getattr(asset, "id", None),
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

    def validate_direct_refs(
        source_id: str, refs: set[str], *, evidence_only: bool = False
    ) -> None:
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
            elif evidence_only and not isinstance(target, Evidence):
                diagnostics.append(
                    Diagnostic(
                        category="evidence",
                        code="evidence.reference_type",
                        message=(
                            f"{source_id} requires Evidence, not "
                            f"{type(target).__name__}: {target_id}"
                        ),
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
        assessment_refs = (
            {ref for refs in assessment.evidence.values() for ref in refs}
            | set(assessment.case_evaluation_refs)
            | set(assessment.readiness_evidence_refs)
        )
        validate_direct_refs("assessment.stage-state", assessment_refs)

    for readiness in readiness_assessments:
        readiness_refs = {
            ref for dimension in readiness.dimensions.values() for ref in dimension.evidence_refs
        }
        validate_direct_refs(readiness.assessment_id, readiness_refs)

    for _source_path, asset in located_assets:
        if not isinstance(asset, Unknown):
            continue
        lifecycle_refs = {ref for entry in asset.history for ref in entry.evidence_refs}
        if asset.closure is not None:
            lifecycle_refs.update(asset.closure.evidence_refs)
        validate_direct_refs(asset.id, lifecycle_refs, evidence_only=True)

    readiness_by_id = {item.assessment_id: item for item in readiness_assessments}
    for approval in autonomy_approvals:
        validate_direct_refs("autonomy-approval", set(approval.evidence_refs), evidence_only=True)
        matching_readiness = readiness_by_id.get(approval.assessment_id)
        if matching_readiness is None:
            diagnostics.append(
                Diagnostic(
                    category="reference",
                    code="approval.assessment_mismatch",
                    message=(
                        "Autonomy approval does not name this workspace's Readiness assessment."
                    ),
                    path="LOOP-READINESS/autonomy-approval.yaml",
                    target_id=approval.assessment_id,
                )
            )
        if manifest is not None:
            try:
                manifest_level = AutonomyLevel(manifest.autonomy_level)
            except ValueError:
                manifest_level = None
            if manifest_level is not None and approval.level is not manifest_level:
                diagnostics.append(
                    Diagnostic(
                        category="evidence",
                        code="approval.level_mismatch",
                        message="Autonomy approval level does not match workspace.yaml.",
                        path="LOOP-READINESS/autonomy-approval.yaml",
                    )
                )
            if approval.owner_id != manifest.owner_id:
                diagnostics.append(
                    Diagnostic(
                        category="evidence",
                        code="approval.owner_mismatch",
                        message="Autonomy approval owner does not match workspace.yaml.",
                        path="LOOP-READINESS/autonomy-approval.yaml",
                    )
                )
        if (
            matching_readiness is not None
            and approval.level.rank > matching_readiness.recommended_ceiling.rank
        ):
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="approval.ceiling_exceeded",
                    message="Autonomy approval exceeds the Readiness ceiling.",
                    path="LOOP-READINESS/autonomy-approval.yaml",
                )
            )
        referenced_evidence = tuple(
            target
            for reference in approval.evidence_refs
            if isinstance((target := identifiers.get(reference)), Evidence)
            and target.status.lower() != "draft"
        )
        if len(referenced_evidence) == len(approval.evidence_refs) and any(
            item.type.value != "owner_confirmation" or item.basis.value != "observed"
            for item in referenced_evidence
        ):
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="approval.evidence_type",
                    message=(
                        "Autonomy approval requires direct observed owner_confirmation Evidence."
                    ),
                    path="LOOP-READINESS/autonomy-approval.yaml",
                )
            )
        if len(referenced_evidence) == len(approval.evidence_refs) and any(
            approval.at < item.captured_at for item in referenced_evidence
        ):
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="approval.evidence_order",
                    message="Autonomy approval cannot predate its supporting Evidence.",
                    path="LOOP-READINESS/autonomy-approval.yaml",
                )
            )

    source_by_path = snapshot.by_path()
    for evidence in evidence_assets:
        source_path = PurePosixPath(evidence.source)
        if (
            source_path.is_absolute()
            or "\\" in evidence.source
            or any(":" in part for part in source_path.parts)
            or ".." in source_path.parts
            or len(source_path.parts) != 3
            or source_path.parts[:2] != ("EVIDENCE", "sources")
            or not source_path.name.startswith(f"{evidence.content_sha256}.")
        ):
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="evidence.source_invalid",
                    message="Evidence source must be a content-addressed normative copy.",
                    asset_id=evidence.id,
                    path=evidence.source,
                )
            )
            continue
        evidence_source = source_by_path.get(source_path.as_posix())
        if evidence_source is None:
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="evidence.source_missing",
                    message="Evidence source copy is missing.",
                    asset_id=evidence.id,
                    path=source_path.as_posix(),
                )
            )
        elif evidence_source.sha256 != evidence.content_sha256:
            diagnostics.append(
                Diagnostic(
                    category="evidence",
                    code="evidence.source_hash",
                    message="Evidence source bytes do not match content_sha256.",
                    asset_id=evidence.id,
                    path=source_path.as_posix(),
                )
            )

    if recorded_index is not None:
        recorded = recorded_index.by_path()
        if len(recorded) != len(recorded_index.entries):
            diagnostics.append(
                Diagnostic(
                    category="filesystem",
                    code="index.path_duplicate",
                    message="Artifact index contains duplicate paths.",
                    path=".foundry/artifact-index.yaml",
                )
            )
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
        for missing_path in sorted(set(recorded) - set(source_by_path)):
            diagnostics.append(
                Diagnostic(
                    category="filesystem",
                    code="source.missing",
                    message="Recorded source is missing from the workspace.",
                    path=missing_path,
                )
            )

    return ValidationReport(diagnostics=tuple(diagnostics))
