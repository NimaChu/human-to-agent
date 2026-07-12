from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from human_to_agent.cli.errors import FoundryError
from human_to_agent.domain.assessment import AssessmentFact, AssessmentSnapshot
from human_to_agent.domain.assets import (
    CaseRecord,
    EvaluationRecord,
    EvaluationResult,
    SkillSpec,
    TaskContract,
    WorkspaceManifest,
)
from human_to_agent.domain.readiness import (
    DimensionStatus,
    ReadinessAssessment,
    ReadinessFacts,
    assess_readiness,
    default_readiness_policy,
)
from human_to_agent.domain.unknowns import Unknown, UnknownStatus
from human_to_agent.repositories.filesystem import SourceRepository, SourceSnapshot
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.validators.workspace import infer_schema_name, validate_workspace

MANAGED_UNKNOWN_STATUSES = {
    UnknownStatus.resolved,
    UnknownStatus.accepted_risk,
    UnknownStatus.human_only,
    UnknownStatus.out_of_scope,
}


@dataclass(frozen=True, slots=True)
class LoadedAssessmentState:
    source: SourceSnapshot
    manifest: WorkspaceManifest
    declared: AssessmentSnapshot
    assessment: AssessmentSnapshot
    models: tuple[BaseModel, ...]
    identifiers: dict[str, BaseModel]
    recorded_index: ArtifactIndex | None

    def require_reference(self, reference: str) -> BaseModel:
        target = self.identifiers.get(reference)
        if target is None:
            raise FoundryError(
                "reference", "reference.missing", f"Evidence reference does not exist: {reference}"
            )
        if str(getattr(target, "status", "")).lower() == "draft":
            raise FoundryError(
                "evidence", "evidence.draft", f"Evidence reference is still draft: {reference}"
            )
        return target


def _load_models(snapshot: SourceSnapshot) -> tuple[BaseModel, ...]:
    models: list[BaseModel] = []
    for source in snapshot.files:
        if source.path.startswith("EVIDENCE/sources/") or not source.path.endswith(
            (".yaml", ".yml")
        ):
            continue
        schema_name = infer_schema_name(source.path)
        if schema_name is None or schema_name not in DEFAULT_MODELS:
            continue
        raw = yaml.safe_load(source.source_path.read_text(encoding="utf-8"))
        models.append(DEFAULT_MODELS[schema_name].model_validate(raw))
    return tuple(models)


def _identifier(model: BaseModel) -> str | None:
    value = getattr(model, "id", None)
    if isinstance(value, str):
        return value
    value = getattr(model, "assessment_id", None)
    return value if isinstance(value, str) else None


def _controlled_fact(
    facts: set[AssessmentFact],
    evidence: dict[AssessmentFact, tuple[str, ...]],
    fact: AssessmentFact,
    refs: tuple[str, ...],
) -> None:
    if refs:
        facts.add(fact)
        evidence[fact] = refs
    else:
        facts.discard(fact)
        evidence.pop(fact, None)


def _computed_assessment(
    manifest: WorkspaceManifest,
    declared: AssessmentSnapshot,
    models: tuple[BaseModel, ...],
) -> AssessmentSnapshot:
    facts = set(declared.facts)
    evidence = dict(declared.evidence)

    cases = {
        item.id: item
        for item in models
        if isinstance(item, CaseRecord) and item.status == "validated"
    }
    evaluations = tuple(
        item
        for item in models
        if isinstance(item, EvaluationRecord)
        and item.status == "validated"
        and item.result is EvaluationResult.passed
        and item.case_ref in cases
    )
    evaluated_case_ids = {item.case_ref for item in evaluations}
    evaluated_case_kinds = frozenset(cases[item].kind for item in evaluated_case_ids)
    case_evaluation_refs = tuple(sorted(item.id for item in evaluations))

    prototype_skills = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, SkillSpec) and item.status.lower() != "draft"
        )
    )
    validated_skills = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, SkillSpec) and item.status == "validated"
        )
    )
    contracts = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, TaskContract) and item.status.lower() != "draft"
        )
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.task_contract_exists, contracts
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.skill_prototype_exists, prototype_skills
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.core_skill_validated, validated_skills
    )

    unknowns = tuple(
        sorted(
            (
                item
                for item in models
                if isinstance(item, Unknown) and item.status.lower() != "draft"
            ),
            key=lambda item: item.id,
        )
    )
    unknown_refs = tuple(item.id for item in unknowns)
    classified_refs = (
        unknown_refs
        if unknowns and all(item.unknown_status is not UnknownStatus.new for item in unknowns)
        else ()
    )
    managed_refs = (
        unknown_refs
        if unknowns and all(item.unknown_status in MANAGED_UNKNOWN_STATUSES for item in unknowns)
        else ()
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.initial_unknowns_recorded, unknown_refs
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.key_unknowns_classified, classified_refs
    )
    _controlled_fact(
        facts, evidence, AssessmentFact.key_unknowns_managed, managed_refs
    )
    _controlled_fact(facts, evidence, AssessmentFact.unknowns_managed, managed_refs)

    readiness_items = tuple(item for item in models if isinstance(item, ReadinessAssessment))
    if len(readiness_items) > 1:
        raise FoundryError(
            "schema", "readiness.duplicate", "Only one Readiness assessment is permitted."
        )
    readiness_result = None
    readiness_refs: tuple[str, ...] = ()
    if readiness_items:
        readiness = readiness_items[0]
        if readiness.workspace_id != manifest.workspace_id:
            raise FoundryError(
                "schema",
                "readiness.workspace_mismatch",
                "Readiness workspace_id does not match workspace.yaml.",
            )
        for key, dimension in readiness.dimensions.items():
            if dimension.dimension is not key:
                raise FoundryError(
                    "schema",
                    "readiness.dimension_mismatch",
                    f"Readiness dimension key does not match {dimension.dimension.value}.",
                )
            if dimension.status is DimensionStatus.satisfied and not dimension.evidence_refs:
                raise FoundryError(
                    "evidence",
                    "readiness.evidence_missing",
                    f"Satisfied Readiness dimension lacks evidence: {key.value}",
                )
        policy = default_readiness_policy()
        if readiness.policy_version != policy.version:
            raise FoundryError(
                "version",
                "readiness.policy_version",
                f"Unsupported Readiness policy version: {readiness.policy_version}",
            )
        recomputed = assess_readiness(
            ReadinessFacts(
                assessment_id=readiness.assessment_id,
                workspace_id=readiness.workspace_id,
                dimensions=readiness.dimensions,
                production_evidence_refs=(),
            ),
            policy,
        )
        expected_ceiling = policy.autonomy_ceiling[readiness.result]
        if (
            readiness.result.rank > recomputed.result.rank
            or readiness.recommended_ceiling.rank > expected_ceiling.rank
        ):
            raise FoundryError(
                "evidence",
                "readiness.overstated",
                "Readiness result exceeds the maturity supported by its dimensions.",
            )
        readiness_result = readiness.result
        readiness_refs = (readiness.assessment_id,)
    _controlled_fact(
        facts, evidence, AssessmentFact.loop_readiness_conclusion, readiness_refs
    )

    return declared.model_copy(
        update={
            "current_stage": manifest.current_stage,
            "facts": frozenset(facts),
            "evidence": evidence,
            "evaluated_case_kinds": evaluated_case_kinds,
            "case_evaluation_refs": case_evaluation_refs,
            "skill_count": len(validated_skills),
            "readiness_result": readiness_result,
            "readiness_evidence_refs": readiness_refs,
        }
    )


def load_assessment_state(
    root: Path,
    workspace_id: str,
    *,
    require_recorded: bool = False,
) -> LoadedAssessmentState:
    try:
        source = SourceRepository(root).snapshot(workspace_id)
    except (FileNotFoundError, ValueError) as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error

    recorded_index = None
    if require_recorded:
        index_path = source.workspace_path / ".foundry/artifact-index.yaml"
        if not index_path.is_file():
            raise FoundryError("filesystem", "index.missing", "Artifact index is missing.")
        try:
            recorded_index = ArtifactIndex.model_validate(
                yaml.safe_load(index_path.read_text(encoding="utf-8"))
            )
        except (ValueError, yaml.YAMLError) as error:
            raise FoundryError("schema", "index.invalid", str(error)) from error

    report = validate_workspace(source, DEFAULT_MODELS, recorded_index=recorded_index)
    if not report.passed:
        first = report.diagnostics[0]
        raise FoundryError(first.category, first.code, first.message)

    models = _load_models(source)
    manifests = tuple(item for item in models if isinstance(item, WorkspaceManifest))
    assessments = tuple(item for item in models if isinstance(item, AssessmentSnapshot))
    if len(manifests) != 1:
        raise FoundryError(
            "schema", "workspace.manifest_count", "Exactly one workspace manifest is required."
        )
    if len(assessments) != 1:
        raise FoundryError(
            "schema",
            "assessment.missing",
            "ASSESSMENTS/stage-state.yaml is required.",
        )
    manifest = manifests[0]
    declared = assessments[0]
    identifiers = {
        identifier: item
        for item in models
        if (identifier := _identifier(item)) is not None
    }
    assessment = _computed_assessment(manifest, declared, models)
    return LoadedAssessmentState(
        source=source,
        manifest=manifest,
        declared=declared,
        assessment=assessment,
        models=models,
        identifiers=identifiers,
        recorded_index=recorded_index,
    )
