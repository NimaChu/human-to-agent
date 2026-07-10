from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: str
    status: str = "ok"
    exit_code: int = 0
    diagnostics: list[dict[str, object]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

