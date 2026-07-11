from __future__ import annotations

from dataclasses import dataclass

EXIT_BY_CATEGORY = {
    "usage": 2,
    "config": 2,
    "schema": 3,
    "reference": 4,
    "evidence": 5,
    "gate": 5,
    "policy": 6,
    "human_gate": 6,
    "version": 7,
    "migration": 7,
    "adapter": 7,
    "filesystem": 8,
    "lock": 8,
    "transaction": 8,
    "event": 9,
    "replay": 9,
}


@dataclass(frozen=True, slots=True)
class FoundryError(Exception):
    category: str
    code: str
    message: str

    @property
    def exit_code(self) -> int:
        return EXIT_BY_CATEGORY[self.category]
