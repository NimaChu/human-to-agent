from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from human_to_agent.domain.common import NonEmptyStr
from human_to_agent.domain.references import ReferenceGraph


class VersionVector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cli: NonEmptyStr
    schema_version: NonEmptyStr
    templates: NonEmptyStr
    skill_catalog: NonEmptyStr
    harness: NonEmptyStr
    tool_contracts: NonEmptyStr
    model_assumptions: NonEmptyStr
    environment_assumptions: NonEmptyStr


class ChangeKind(StrEnum):
    skill_contract = "skill_contract"
    harness_core = "harness_core"
    tool_permission = "tool_permission"
    tool_side_effect = "tool_side_effect"
    schema_major = "schema_major"
    golden_case = "golden_case"
    invalidated_assumption = "invalidated_assumption"


class MaterialChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ChangeKind
    asset_id: NonEmptyStr
    description: NonEmptyStr = "Material contract change"


class RecertificationCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: NonEmptyStr
    evaluations_by_kind: dict[ChangeKind, tuple[NonEmptyStr, ...]]
    blocking_kinds: frozenset[ChangeKind]


class RecertificationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    change: MaterialChange
    catalog_version: NonEmptyStr
    asset_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    required_evaluations: tuple[NonEmptyStr, ...] = Field(min_length=1)
    reasons: tuple[NonEmptyStr, ...] = Field(min_length=1)
    blocking: bool


def default_recertification_catalog() -> RecertificationCatalog:
    return RecertificationCatalog(
        version="1",
        evaluations_by_kind={
            ChangeKind.skill_contract: ("skill_cases", "dependent_contracts"),
            ChangeKind.harness_core: ("stage4_e2e", "stage5_readiness"),
            ChangeKind.tool_permission: ("policy_matrix", "human_gate_matrix"),
            ChangeKind.tool_side_effect: (
                "policy_matrix",
                "human_gate_matrix",
                "idempotency_retry",
            ),
            ChangeKind.schema_major: (
                "full_schema_validation",
                "migration_roundtrip",
                "stage5_readiness",
            ),
            ChangeKind.golden_case: ("skill_cases", "stage4_e2e"),
            ChangeKind.invalidated_assumption: (
                "full_schema_validation",
                "affected_cases",
                "stage5_readiness",
            ),
        },
        blocking_kinds=frozenset(
            {
                ChangeKind.harness_core,
                ChangeKind.tool_permission,
                ChangeKind.tool_side_effect,
                ChangeKind.schema_major,
                ChangeKind.invalidated_assumption,
            }
        ),
    )


def plan_recertification(
    change: MaterialChange,
    graph: ReferenceGraph,
    catalog: RecertificationCatalog,
) -> RecertificationPlan:
    impacted = {change.asset_id, *graph.reverse_dependents(change.asset_id)}
    evaluations = set(catalog.evaluations_by_kind[change.kind])
    if change.kind is ChangeKind.harness_core:
        evaluations.update({"stage4_e2e", "stage5_readiness"})
    if change.kind in {ChangeKind.schema_major, ChangeKind.invalidated_assumption}:
        evaluations.update({"full_schema_validation", "stage5_readiness"})
    return RecertificationPlan(
        change=change,
        catalog_version=catalog.version,
        asset_ids=tuple(sorted(impacted)),
        required_evaluations=tuple(sorted(evaluations)),
        reasons=(
            f"{change.kind.value} changed {change.asset_id}",
            "Reverse dependencies must be re-certified against the changed contract.",
        ),
        blocking=change.kind in catalog.blocking_kinds,
    )


RECERTIFICATION_MODELS: dict[str, type[BaseModel]] = {
    "recertification-plan": RecertificationPlan,
    "version-vector": VersionVector,
}
