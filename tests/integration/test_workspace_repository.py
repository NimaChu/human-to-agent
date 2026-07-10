from pathlib import Path

import pytest

from harness_foundry.repositories.filesystem import SourceRepository, tree_digest


def make_workspace(root: Path) -> Path:
    workspace = root / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    (workspace / "workspace.yaml").write_text("b: 2\na: 1\n", encoding="utf-8")
    (workspace / "README.md").write_bytes(b"# Pilot\r\n")
    (workspace / ".foundry" / "locks").mkdir(parents=True)
    (workspace / ".foundry" / "locks" / "writer.lock").write_text("runtime")
    (workspace / ".foundry" / "transactions").mkdir(parents=True)
    (workspace / ".foundry" / "transactions" / "tx.json").write_text("runtime")
    (workspace / "dist").mkdir()
    (workspace / "dist" / "generated.md").write_text("generated")
    return workspace


def test_snapshot_uses_posix_paths_and_excludes_runtime_and_generated_files(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    repository = SourceRepository(tmp_path)
    snapshot = repository.snapshot("pilot")
    assert tuple(item.path for item in snapshot.files) == ("README.md", "workspace.yaml")


def test_yaml_digest_ignores_key_order_and_crlf(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    repository = SourceRepository(tmp_path)
    first = tree_digest(repository.snapshot("pilot"))
    (workspace / "workspace.yaml").write_bytes(b"a: 1\r\nb: 2\r\n")
    second = tree_digest(repository.snapshot("pilot"))
    assert first == second


def test_validation_snapshot_does_not_rewrite_source_bytes(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    before = (workspace / "README.md").read_bytes()
    SourceRepository(tmp_path).snapshot("pilot")
    assert (workspace / "README.md").read_bytes() == before


def test_workspace_slug_cannot_escape_workspace_root(tmp_path: Path) -> None:
    (tmp_path / "workspaces").mkdir()
    with pytest.raises(ValueError, match="outside workspace root"):
        SourceRepository(tmp_path).snapshot("../PR")
