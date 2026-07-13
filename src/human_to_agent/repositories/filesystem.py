from __future__ import annotations

import stat as stat_module
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

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
NON_NORMATIVE_ASSET_DIRECTORIES = frozenset({"ASSETS", "DATA"})


def is_non_normative_asset_path(path: str) -> bool:
    return path.split("/", 1)[0] in NON_NORMATIVE_ASSET_DIRECTORIES


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    reparse_point = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_point)


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
        workspace_root = self.repository_root / "workspaces"
        if _is_link_or_junction(workspace_root):
            raise ValueError("workspace root cannot be a symlink or junction")
        self.workspace_root = workspace_root.resolve()
        if not self.workspace_root.is_relative_to(self.repository_root):
            raise ValueError("workspace root resolves outside repository")

    def workspace_path(self, slug: str) -> Path:
        identifier = PurePosixPath(slug)
        if (
            len(identifier.parts) != 1
            or identifier.as_posix() in {"", ".", ".."}
            or "\\" in slug
            or ":" in slug
        ):
            raise ValueError("workspace id must be a single safe path component")
        workspace_path = self.workspace_root / slug
        if _is_link_or_junction(workspace_path):
            raise ValueError("workspace path cannot be a symlink or junction")
        candidate = workspace_path.resolve()
        if not candidate.is_relative_to(self.workspace_root):
            raise ValueError("workspace path is outside workspace root")
        if not candidate.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {slug}")
        return candidate

    def snapshot(self, slug: str) -> SourceSnapshot:
        workspace = self.workspace_path(slug)
        files: list[SourceFile] = []
        for path in workspace.rglob("*"):
            relative = path.relative_to(workspace)
            if _is_link_or_junction(path):
                raise ValueError(
                    f"workspace source cannot be a symlink or junction: {relative.as_posix()}"
                )
            resolved = path.resolve()
            if not resolved.is_relative_to(workspace):
                raise ValueError(
                    f"workspace source resolves outside workspace: {relative.as_posix()}"
                )
            if not path.is_file():
                continue
            if any(part in _EXCLUDED_PARTS for part in relative.parts):
                continue
            relative_path = relative.as_posix()
            canonical = (
                resolved.read_bytes()
                if relative.parts[:2] == ("EVIDENCE", "sources")
                or is_non_normative_asset_path(relative_path)
                else canonical_file(resolved)
            )
            files.append(
                SourceFile(
                    path=relative_path,
                    source_path=resolved,
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
