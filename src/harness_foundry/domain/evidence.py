from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from harness_foundry.domain.common import AssetMetadata, NonEmptyStr, require_aware_utc


class EvidenceBasis(StrEnum):
    observed = "observed"
    inferred = "inferred"
    assumption = "assumption"
    unverified = "unverified"


class EvidenceType(StrEnum):
    formal_rule = "formal_rule"
    real_case = "real_case"
    owner_confirmation = "owner_confirmation"
    system_definition = "system_definition"
    historical_data = "historical_data"
    risk_decision = "risk_decision"
    repeatable_validation = "repeatable_validation"


class Evidence(AssetMetadata):
    type: EvidenceType
    source: NonEmptyStr
    locator: NonEmptyStr
    captured_by: NonEmptyStr
    captured_at: datetime
    content_summary: NonEmptyStr
    claim: NonEmptyStr
    basis: EvidenceBasis
    applicability_scope: tuple[NonEmptyStr, ...] = Field(min_length=1)
    validity_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cheapest_probe: NonEmptyStr | None = None

    @field_validator("captured_at")
    @classmethod
    def captured_at_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @model_validator(mode="after")
    def low_confidence_requires_probe(self) -> Evidence:
        if (
            self.basis in {EvidenceBasis.assumption, EvidenceBasis.unverified}
            and self.cheapest_probe is None
        ):
            raise ValueError("cheapest_probe is required for low-confidence evidence")
        return self
