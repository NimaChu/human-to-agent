from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness_foundry.domain.common import NonEmptyStr, require_aware_utc


class ReadinessDimension(StrEnum):
    goal = "goal"
    state = "state"
    action = "action"
    evaluator = "evaluator"
    stop = "stop"
    budget = "budget"
    retry = "retry"
    escalation = "escalation"
    recovery = "recovery"
    observability = "observability"
    trigger_cadence = "trigger_cadence"
    discovery_triage = "discovery_triage"
    concurrency_isolation = "concurrency_isolation"
    tool_connector_availability = "tool_connector_availability"
    independent_verifier = "independent_verifier"
    version_drift_recertification = "version_drift_recertification"


CORE_DIMENSIONS = tuple(ReadinessDimension)[:10]


class DimensionStatus(StrEnum):
    satisfied = "satisfied"
    gap = "gap"
    indeterminate = "indeterminate"


class ReadinessResult(StrEnum):
    not_ready = "not_ready"
    conditional_ready = "conditional_ready"
    controlled_ready = "controlled_ready"
    bounded_ready = "bounded_ready"
    production_candidate = "production_candidate"

    @property
    def rank(self) -> int:
        return tuple(ReadinessResult).index(self)


class AutonomyLevel(StrEnum):
    h0 = "h0"
    h1 = "h1"
    h2 = "h2"
    h3 = "h3"
    h4 = "h4"
    h5 = "h5"

    @property
    def rank(self) -> int:
        return tuple(AutonomyLevel).index(self)


class DimensionAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: ReadinessDimension
    status: DimensionStatus
    evidence_refs: tuple[NonEmptyStr, ...]
    gaps: tuple[NonEmptyStr, ...]
    risks: tuple[NonEmptyStr, ...]
    next_action: NonEmptyStr | None = None

    @property
    def is_indeterminate(self) -> bool:
        return self.status is DimensionStatus.indeterminate

    @classmethod
    def satisfied(
        cls,
        dimension: ReadinessDimension,
        *,
        evidence_refs: tuple[str, ...],
    ) -> DimensionAssessment:
        if not evidence_refs:
            raise ValueError("satisfied dimensions require evidence")
        return cls(
            dimension=dimension,
            status=DimensionStatus.satisfied,
            evidence_refs=evidence_refs,
            gaps=(),
            risks=(),
        )

    @classmethod
    def gap(
        cls,
        dimension: ReadinessDimension,
        gap: str,
        *,
        risks: tuple[str, ...] = (),
        next_action: str | None = None,
    ) -> DimensionAssessment:
        return cls(
            dimension=dimension,
            status=DimensionStatus.gap,
            evidence_refs=(),
            gaps=(gap,),
            risks=risks,
            next_action=next_action,
        )

    @classmethod
    def indeterminate(
        cls,
        dimension: ReadinessDimension,
        gap: str,
    ) -> DimensionAssessment:
        return cls(
            dimension=dimension,
            status=DimensionStatus.indeterminate,
            evidence_refs=(),
            gaps=(gap,),
            risks=(f"{dimension.value} cannot be evaluated",),
            next_action=f"Provide evidence for {dimension.value}.",
        )


class ReadinessFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: NonEmptyStr
    workspace_id: NonEmptyStr
    dimensions: dict[ReadinessDimension, DimensionAssessment]
    production_evidence_refs: tuple[NonEmptyStr, ...]

    def with_dimension(
        self,
        dimension: ReadinessDimension,
        assessment: DimensionAssessment,
    ) -> ReadinessFacts:
        if assessment.dimension is not dimension:
            raise ValueError("dimension key and assessment dimension must match")
        values = dict(self.dimensions)
        values[dimension] = assessment
        return self.model_copy(update={"dimensions": values})


class ReadinessPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: NonEmptyStr
    requirements: dict[ReadinessResult, tuple[ReadinessDimension, ...]]
    autonomy_ceiling: dict[ReadinessResult, AutonomyLevel]
    production_evidence_minimum: int = Field(ge=1)


class ReadinessAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assessment_id: NonEmptyStr
    workspace_id: NonEmptyStr
    policy_version: NonEmptyStr
    result: ReadinessResult
    dimensions: dict[ReadinessDimension, DimensionAssessment]
    evidence_gaps: tuple[NonEmptyStr, ...]
    risks: tuple[NonEmptyStr, ...]
    next_actions: tuple[NonEmptyStr, ...]
    recommended_ceiling: AutonomyLevel
    approved_autonomy: None = None


class AutonomyApproval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: NonEmptyStr
    assessment_id: NonEmptyStr
    level: AutonomyLevel
    owner_id: NonEmptyStr
    at: datetime
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @field_validator("at")
    @classmethod
    def at_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


def default_readiness_policy() -> ReadinessPolicy:
    controlled = (
        *CORE_DIMENSIONS,
        ReadinessDimension.tool_connector_availability,
        ReadinessDimension.independent_verifier,
        ReadinessDimension.version_drift_recertification,
    )
    all_dimensions = tuple(ReadinessDimension)
    return ReadinessPolicy(
        version="1",
        requirements={
            ReadinessResult.conditional_ready: CORE_DIMENSIONS,
            ReadinessResult.controlled_ready: controlled,
            ReadinessResult.bounded_ready: all_dimensions,
            ReadinessResult.production_candidate: all_dimensions,
        },
        autonomy_ceiling={
            ReadinessResult.not_ready: AutonomyLevel.h0,
            ReadinessResult.conditional_ready: AutonomyLevel.h1,
            ReadinessResult.controlled_ready: AutonomyLevel.h3,
            ReadinessResult.bounded_ready: AutonomyLevel.h5,
            ReadinessResult.production_candidate: AutonomyLevel.h5,
        },
        production_evidence_minimum=2,
    )


def _requirements_satisfied(
    dimensions: dict[ReadinessDimension, DimensionAssessment],
    requirements: tuple[ReadinessDimension, ...],
) -> bool:
    return all(
        dimensions[dimension].status is DimensionStatus.satisfied for dimension in requirements
    )


def assess_readiness(
    facts: ReadinessFacts,
    policy: ReadinessPolicy,
) -> ReadinessAssessment:
    dimensions = dict(facts.dimensions)
    for dimension in ReadinessDimension:
        dimensions.setdefault(
            dimension,
            DimensionAssessment.indeterminate(dimension, f"No evidence for {dimension.value}"),
        )

    result = ReadinessResult.not_ready
    for candidate in (
        ReadinessResult.conditional_ready,
        ReadinessResult.controlled_ready,
        ReadinessResult.bounded_ready,
    ):
        if _requirements_satisfied(dimensions, policy.requirements[candidate]):
            result = candidate
    if (
        _requirements_satisfied(
            dimensions,
            policy.requirements[ReadinessResult.production_candidate],
        )
        and len(facts.production_evidence_refs) >= policy.production_evidence_minimum
    ):
        result = ReadinessResult.production_candidate

    gaps = tuple(
        f"{dimension.value}: {gap}"
        for dimension, assessment in sorted(dimensions.items(), key=lambda item: item[0].value)
        for gap in assessment.gaps
    )
    risks = tuple(
        risk
        for _, assessment in sorted(dimensions.items(), key=lambda item: item[0].value)
        for risk in assessment.risks
    )
    next_actions = tuple(
        assessment.next_action
        for _, assessment in sorted(dimensions.items(), key=lambda item: item[0].value)
        if assessment.next_action is not None
    )
    return ReadinessAssessment(
        assessment_id=facts.assessment_id,
        workspace_id=facts.workspace_id,
        policy_version=policy.version,
        result=result,
        dimensions=dimensions,
        evidence_gaps=gaps,
        risks=risks,
        next_actions=next_actions,
        recommended_ceiling=policy.autonomy_ceiling[result],
    )


def record_autonomy_approval(
    assessment: ReadinessAssessment,
    level: AutonomyLevel,
    *,
    owner_id: str,
    at: datetime,
    evidence_refs: tuple[str, ...],
) -> AutonomyApproval:
    owner_id = owner_id.strip()
    if not owner_id:
        raise ValueError("owner is required for autonomy approval")
    if level.rank > assessment.recommended_ceiling.rank:
        raise ValueError("approved autonomy cannot exceed the recommended ceiling")
    if not evidence_refs:
        raise ValueError("autonomy approval evidence is required")
    return AutonomyApproval(
        workspace_id=assessment.workspace_id,
        assessment_id=assessment.assessment_id,
        level=level,
        owner_id=owner_id,
        at=at,
        evidence_refs=evidence_refs,
    )


READINESS_MODELS: dict[str, type[BaseModel]] = {
    "autonomy-approval": AutonomyApproval,
    "readiness-assessment": ReadinessAssessment,
    "readiness-policy": ReadinessPolicy,
}
