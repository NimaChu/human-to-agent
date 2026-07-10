from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness_foundry.domain.common import AssetMetadata, NonEmptyStr, require_aware_utc
from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType


class UnknownCategory(StrEnum):
    goal = "goal"
    input = "input"
    rule = "rule"
    judgment = "judgment"
    exception = "exception"
    acceptance = "acceptance"
    permission = "permission"
    tool = "tool"
    state = "state"
    boundary = "boundary"
    risk = "risk"
    responsibility = "responsibility"


class UnknownStatus(StrEnum):
    new = "new"
    clarification = "clarification"
    evidence = "evidence"
    business_confirmation = "business_confirmation"
    validation = "validation"
    resolved = "resolved"
    accepted_risk = "accepted_risk"
    human_only = "human_only"
    out_of_scope = "out_of_scope"
    reopened = "reopened"


class UnknownDisposition(StrEnum):
    resolved = "resolved"
    accepted_risk = "accepted_risk"
    human_only = "human_only"
    out_of_scope = "out_of_scope"


class UnknownClosure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    disposition: UnknownDisposition
    owner_id: NonEmptyStr
    actor: NonEmptyStr
    at: datetime
    conclusion: NonEmptyStr
    impact: NonEmptyStr
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    propagated_to: tuple[NonEmptyStr, ...]

    @field_validator("at")
    @classmethod
    def at_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class UnknownHistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_status: UnknownStatus
    to_status: UnknownStatus
    reason: NonEmptyStr
    actor: NonEmptyStr
    at: datetime
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @field_validator("at")
    @classmethod
    def at_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class Unknown(AssetMetadata):
    title: NonEmptyStr
    description: NonEmptyStr
    category: UnknownCategory
    unknown_status: UnknownStatus
    impact_dimensions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    impact_narrative: NonEmptyStr
    occurrence_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    affected_assets: tuple[NonEmptyStr, ...] = Field(min_length=1)
    confidence_basis: EvidenceBasis
    owner_id: NonEmptyStr
    expected_responder_role: NonEmptyStr
    cheapest_probe: NonEmptyStr
    prompt_patch: NonEmptyStr
    automation_restriction: NonEmptyStr
    allowed_closure_evidence: tuple[EvidenceType, ...] = Field(min_length=1)
    fact_resolved: bool = False
    closure: UnknownClosure | None = None
    history: tuple[UnknownHistoryEntry, ...] = ()


_STATUS_BY_DISPOSITION = {
    UnknownDisposition.resolved: UnknownStatus.resolved,
    UnknownDisposition.accepted_risk: UnknownStatus.accepted_risk,
    UnknownDisposition.human_only: UnknownStatus.human_only,
    UnknownDisposition.out_of_scope: UnknownStatus.out_of_scope,
}


def close_unknown(
    item: Unknown,
    closure: UnknownClosure,
    evidence: Mapping[str, Evidence],
) -> Unknown:
    if closure.owner_id != item.owner_id:
        raise ValueError("closure owner must match the Unknown owner")
    if not closure.propagated_to:
        raise ValueError("closure propagation targets are required")

    missing = tuple(ref for ref in closure.evidence_refs if ref not in evidence)
    if missing:
        raise ValueError(f"missing evidence: {', '.join(missing)}")

    allowed = set(item.allowed_closure_evidence)
    if not any(evidence[ref].type in allowed for ref in closure.evidence_refs):
        raise ValueError("closure requires at least one allowed evidence type")

    target_status = _STATUS_BY_DISPOSITION[closure.disposition]
    entry = UnknownHistoryEntry(
        from_status=item.unknown_status,
        to_status=target_status,
        reason=f"Closed as {closure.disposition.value}: {closure.conclusion}",
        actor=closure.actor,
        at=closure.at,
        evidence_refs=closure.evidence_refs,
    )
    return item.model_copy(
        update={
            "revision": item.revision + 1,
            "updated_at": closure.at,
            "unknown_status": target_status,
            "fact_resolved": closure.disposition is UnknownDisposition.resolved,
            "closure": closure,
            "history": (*item.history, entry),
        }
    )


def reopen_unknown(
    item: Unknown,
    *,
    reason: str,
    actor: str,
    at: datetime,
    evidence_refs: tuple[str, ...],
) -> Unknown:
    reason = reason.strip()
    actor = actor.strip()
    if not reason:
        raise ValueError("reopen reason is required")
    if not actor:
        raise ValueError("reopen actor is required")
    if not evidence_refs:
        raise ValueError("reopen evidence is required")
    at = require_aware_utc(at)
    entry = UnknownHistoryEntry(
        from_status=item.unknown_status,
        to_status=UnknownStatus.reopened,
        reason=reason,
        actor=actor,
        at=at,
        evidence_refs=evidence_refs,
    )
    return item.model_copy(
        update={
            "revision": item.revision + 1,
            "updated_at": at,
            "unknown_status": UnknownStatus.reopened,
            "fact_resolved": False,
            "history": (*item.history, entry),
        }
    )


UNKNOWN_MODELS: dict[str, type[AssetMetadata]] = {"unknown": Unknown}
