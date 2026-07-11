from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from human_to_agent.domain.common import NonEmptyStr, require_aware_utc


class EventScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    scope_id: NonEmptyStr
    log_path: Path


class EventDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: NonEmptyStr
    workspace_id: NonEmptyStr
    at: datetime
    actor: NonEmptyStr
    command: NonEmptyStr
    asset_refs: tuple[NonEmptyStr, ...] = ()
    before_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: NonEmptyStr
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class StoredEvent(EventDraft):
    sequence: int = Field(ge=1)
    prev_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class EventVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    errors: tuple[str, ...] = ()
    event_count: int = Field(ge=0)
    last_digest: str | None = None


class ReplayResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    events: tuple[StoredEvent, ...] = ()


EVENT_MODELS: dict[str, type[BaseModel]] = {
    "event-scope": EventScope,
    "event-draft": EventDraft,
    "stored-event": StoredEvent,
    "event-verification": EventVerification,
    "event-replay": ReplayResult,
}
