from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness_foundry.domain.common import NonEmptyStr


class ArtifactIndexEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: NonEmptyStr
    path: NonEmptyStr
    revision: int = Field(ge=1)
    asset_schema_version: NonEmptyStr
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArtifactIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: NonEmptyStr
    entries: tuple[ArtifactIndexEntry, ...]

    def by_path(self) -> dict[str, ArtifactIndexEntry]:
        return {item.path: item for item in self.entries}
