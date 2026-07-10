from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")
    return value.astimezone(UTC)


class AssetMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: NonEmptyStr
    id: NonEmptyStr
    workspace_id: NonEmptyStr
    revision: int = Field(ge=1)
    status: NonEmptyStr
    owners: tuple[NonEmptyStr, ...] = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    provenance: NonEmptyStr
    links: tuple[NonEmptyStr, ...] = ()
    evidence_refs: tuple[NonEmptyStr, ...] = ()

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @model_validator(mode="after")
    def update_is_not_before_creation(self) -> AssetMetadata:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
        return self
