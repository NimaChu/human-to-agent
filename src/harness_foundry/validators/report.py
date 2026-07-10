from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness_foundry.domain.common import NonEmptyStr


class Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: NonEmptyStr
    code: NonEmptyStr
    message: NonEmptyStr
    path: NonEmptyStr | None = None
    asset_id: NonEmptyStr | None = None
    target_id: NonEmptyStr | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostics: tuple[Diagnostic, ...]

    @property
    def passed(self) -> bool:
        return not self.diagnostics
