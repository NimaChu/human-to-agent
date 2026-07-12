from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from human_to_agent.repositories.canonical import canonical_file

_EXCLUDED_PARTS = {
    ".foundry",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
}


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    source_path: Path
    canonical_content: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    slug: str
    workspace_path: Path
    files: tuple[SourceFile, ...]

    def by_path(self) -> dict[str, SourceFile]:
        return {item.path: item for item in self.files}


class SourceRepository:
    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.workspace_root = (self.repository_root / "workspaces").resolve()

    def workspace_path(self, slug: str) -> Path:
        candidate = (self.workspace_root / slug).resolve()
        if not candidate.is_relative_to(self.workspace_root):
            raise ValueError("workspace path is outside workspace root")
        if not candidate.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {slug}")
        return candidate

    def snapshot(self, slug: str) -> SourceSnapshot:
        workspace = self.workspace_path(slug)
        files: list[SourceFile] = []
        for path in workspace.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(workspace)
            if any(part in _EXCLUDED_PARTS for part in relative.parts):
                continue
            canonical = (
                path.read_bytes()
                if relative.parts[:2] == ("EVIDENCE", "sources")
                else canonical_file(path)
            )
            files.append(
                SourceFile(
                    path=relative.as_posix(),
                    source_path=path,
                    canonical_content=canonical,
                    sha256=sha256(canonical).hexdigest(),
                )
            )
        return SourceSnapshot(
            slug=slug,
            workspace_path=workspace,
            files=tuple(sorted(files, key=lambda item: item.path)),
        )


def tree_digest(snapshot: SourceSnapshot) -> str:
    digest = sha256()
    for item in snapshot.files:
        digest.update(item.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
