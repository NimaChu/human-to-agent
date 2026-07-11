from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class BuildMode(StrEnum):
    draft = "draft"
    release = "release"


@dataclass(frozen=True, slots=True)
class BuildPlan:
    workspace_id: str
    mode: BuildMode
    destination: Path
    source_digest: str
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class BuildResult:
    path: Path
    mode: BuildMode
    source_digest: str
    changed_files: tuple[str, ...]
    published: bool
