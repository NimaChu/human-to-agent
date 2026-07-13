from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import yaml
from pydantic import BaseModel

from human_to_agent.cli.errors import FoundryError
from human_to_agent.domain.assessment import AssessmentFact, AssessmentSnapshot
from human_to_agent.domain.assets import (
    ActionClass,
    CaseKind,
    CaseRecord,
    ContextSpec,
    EvaluationRecord,
    EvaluationResult,
    EvaluatorSpec,
    ExceptionSpec,
    HarnessSpec,
    HumanGateSpec,
    PolicySpec,
    RunRecord,
    SkillSpec,
    StateModelSpec,
    TaskContract,
    ToolSpec,
    WorkflowSpec,
    WorkspaceManifest,
)
from human_to_agent.domain.evidence import Evidence
from human_to_agent.domain.readiness import (
    AutonomyApproval,
    AutonomyLevel,
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
    if isinstance(model, AutonomyApproval):
        return None
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


def _current_input_digest(source: SourceSnapshot) -> str:
    digest = sha256()
    for item in source.files:
        if item.path.startswith("RUNS/"):
            continue
        digest.update(item.path.encode())
        digest.update(b"\0")
        digest.update(item.sha256.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _computed_assessment(
    source: SourceSnapshot,
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
    normal_evaluation_refs = tuple(
        sorted(item.id for item in evaluations if cases[item.case_ref].kind is CaseKind.normal)
    )
    failure_evaluation_refs = tuple(
        sorted(item.id for item in evaluations if cases[item.case_ref].kind is CaseKind.failure)
    )

    prototype_skills = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, SkillSpec) and item.status.lower() != "draft"
        )
    )
    validated_skills = tuple(
        sorted(
            item.id for item in models if isinstance(item, SkillSpec) and item.status == "validated"
        )
    )
    contracts = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, TaskContract) and item.status.lower() != "draft"
        )
    )
    validated_contracts = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, TaskContract) and item.status == "validated"
        )
    )
    _controlled_fact(facts, evidence, AssessmentFact.task_contract_exists, contracts)
    _controlled_fact(facts, evidence, AssessmentFact.business_goal_clear, validated_contracts)
    _controlled_fact(facts, evidence, AssessmentFact.task_contract_complete, validated_contracts)
    _controlled_fact(facts, evidence, AssessmentFact.skill_prototype_exists, prototype_skills)
    _controlled_fact(facts, evidence, AssessmentFact.core_skill_validated, validated_skills)
    _controlled_fact(facts, evidence, AssessmentFact.normal_paths_stable, normal_evaluation_refs)
    _controlled_fact(
        facts, evidence, AssessmentFact.common_failures_detected, failure_evaluation_refs
    )
    _controlled_fact(facts, evidence, AssessmentFact.result_evaluable, case_evaluation_refs)

    expected_input_digest = _current_input_digest(source)
    runs = tuple(
        item
        for item in models
        if isinstance(item, RunRecord)
        and item.status == "validated"
        and item.passed
        and item.input_tree_digest == expected_input_digest
    )
    original_case_runs = tuple(sorted(item.id for item in runs if item.case_ref in cases))
    independent_skill_runs = tuple(
        sorted(
            item.id
            for item in runs
            if item.actor_role == "independent_verifier" and item.skill_ref in validated_skills
        )
    )
    _controlled_fact(facts, evidence, AssessmentFact.original_case_rerun, original_case_runs)
    _controlled_fact(facts, evidence, AssessmentFact.independent_skill_run, independent_skill_runs)

    workflows = {
        item.id: item
        for item in models
        if isinstance(item, WorkflowSpec) and item.status == "validated"
    }
    harnesses = tuple(
        item
        for item in models
        if isinstance(item, HarnessSpec)
        and item.status == "validated"
        and item.workflow_ref in workflows
    )
    harness_workflows = {item.workflow_ref for item in harnesses}
    harness_runs = tuple(item for item in runs if item.workflow_ref in harness_workflows)
    independent_harness_runs = tuple(
        item for item in harness_runs if item.actor_role == "independent_verifier"
    )
    contexts = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, ContextSpec) and item.status == "validated"
        )
    )
    states = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, StateModelSpec) and item.status == "validated"
        )
    )
    policies = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, PolicySpec) and item.status == "validated"
        )
    )
    gates = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, HumanGateSpec) and item.status == "validated"
        )
    )
    exceptions = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, ExceptionSpec) and item.status == "validated"
        )
    )
    evaluators = tuple(
        sorted(
            item.id
            for item in models
            if isinstance(item, EvaluatorSpec) and item.status == "validated"
        )
    )
    final_evaluators = tuple(
        sorted(
            {
                reference
                for workflow in workflows.values()
                if workflow.final_evaluator_ref in evaluators
                for reference in (workflow.id, workflow.final_evaluator_ref)
            }
        )
    )
    high_risk_tools = tuple(
        item
        for item in models
        if isinstance(item, ToolSpec)
        and item.status == "validated"
        and item.action_class in {ActionClass.external_send, ActionClass.irreversible}
    )
    high_risk_gate_refs = (
        tuple(sorted({*gates, *(item.id for item in high_risk_tools)}))
        if gates and all(item.human_gate_ref in gates for item in high_risk_tools)
        else ()
    )
    boundary_refs = (
        tuple(sorted({*validated_contracts, *validated_skills, *states}))
        if validated_contracts and validated_skills and states
        else ()
    )
    exception_detection_refs = (
        tuple(sorted({*exceptions, *failure_evaluation_refs}))
        if exceptions and failure_evaluation_refs
        else ()
    )
    harness_run_refs = tuple(sorted(item.id for item in harness_runs))
    independent_harness_refs = tuple(sorted(item.id for item in independent_harness_runs))
    trace_refs = tuple(sorted({*harness_run_refs, *harness_workflows})) if harness_run_refs else ()
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.end_to_end_harness_run,
        harness_run_refs,
    )
    _controlled_fact(facts, evidence, AssessmentFact.steps_traceable, trace_refs)
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.harness_goal_and_completion,
        tuple(sorted(item.id for item in harnesses)),
    )
    _controlled_fact(facts, evidence, AssessmentFact.context_defined, contexts)
    _controlled_fact(facts, evidence, AssessmentFact.state_defined, states)
    _controlled_fact(facts, evidence, AssessmentFact.policies_defined, policies)
    _controlled_fact(facts, evidence, AssessmentFact.human_gates_defined, gates)
    _controlled_fact(facts, evidence, AssessmentFact.exceptions_defined, exceptions)
    _controlled_fact(facts, evidence, AssessmentFact.local_evaluators_defined, evaluators)
    _controlled_fact(facts, evidence, AssessmentFact.final_evaluator_defined, final_evaluators)
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.noncreator_harness_run,
        independent_harness_refs,
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.input_output_state_boundaries_clear,
        boundary_refs,
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.key_exceptions_detectable,
        exception_detection_refs,
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.high_risk_actions_have_human_gates,
        high_risk_gate_refs,
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.stop_recovery_escalation_defined,
        tuple(sorted({*policies, *exceptions})) if policies and exceptions else (),
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.noncreator_can_maintain,
        independent_harness_refs,
    )

    unknowns = tuple(
        sorted(
            (item for item in models if isinstance(item, Unknown)),
            key=lambda item: item.id,
        )
    )
    unknown_refs = tuple(item.id for item in unknowns if item.status.lower() != "draft")
    all_unknowns_are_recorded = bool(unknowns) and len(unknown_refs) == len(unknowns)
    classified_refs = (
        unknown_refs
        if all_unknowns_are_recorded
        and all(item.unknown_status is not UnknownStatus.new for item in unknowns)
        else ()
    )
    managed_refs = (
        unknown_refs
        if all_unknowns_are_recorded
        and all(item.unknown_status in MANAGED_UNKNOWN_STATUSES for item in unknowns)
        else ()
    )
    _controlled_fact(
        facts,
        evidence,
        AssessmentFact.initial_unknowns_recorded,
        unknown_refs if all_unknowns_are_recorded else (),
    )
    _controlled_fact(facts, evidence, AssessmentFact.key_unknowns_classified, classified_refs)
    _controlled_fact(facts, evidence, AssessmentFact.key_unknowns_managed, managed_refs)
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
    _controlled_fact(facts, evidence, AssessmentFact.loop_readiness_conclusion, readiness_refs)
    autonomy_refs: tuple[str, ...] = ()
    approvals = tuple(item for item in models if isinstance(item, AutonomyApproval))
    valid_evidence = {
        item.id: item
        for item in models
        if isinstance(item, Evidence) and item.status.lower() != "draft"
    }
    if readiness_items and manifest.status == "validated":
        try:
            autonomy = AutonomyLevel(manifest.autonomy_level)
        except ValueError as error:
            raise FoundryError(
                "schema",
                "workspace.autonomy_invalid",
                f"Unknown autonomy level: {manifest.autonomy_level}",
            ) from error
        readiness = readiness_items[0]
        matching = tuple(
            approval
            for approval in approvals
            if approval.workspace_id == manifest.workspace_id
            and approval.assessment_id == readiness.assessment_id
            and approval.level is autonomy
            and approval.owner_id == manifest.owner_id
            and approval.level.rank <= readiness.recommended_ceiling.rank
            and all(reference in valid_evidence for reference in approval.evidence_refs)
            and all(
                valid_evidence[reference].type.value == "owner_confirmation"
                and valid_evidence[reference].basis.value == "observed"
                for reference in approval.evidence_refs
            )
            and all(
                approval.at >= valid_evidence[reference].captured_at
                for reference in approval.evidence_refs
            )
        )
        if len(matching) == 1:
            autonomy_refs = matching[0].evidence_refs
    _controlled_fact(facts, evidence, AssessmentFact.autonomy_approved, autonomy_refs)

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
        identifier: item for item in models if (identifier := _identifier(item)) is not None
    }
    assessment = _computed_assessment(source, manifest, declared, models)
    return LoadedAssessmentState(
        source=source,
        manifest=manifest,
        declared=declared,
        assessment=assessment,
        models=models,
        identifiers=identifiers,
        recorded_index=recorded_index,
    )
