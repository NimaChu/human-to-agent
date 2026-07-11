import json
from hashlib import sha256
from pathlib import Path

import pytest

from human_to_agent.domain.builds import BuildMode
from human_to_agent.services.build import Builder
from human_to_agent.services.distribution_verify import verify_distribution


def digest_tree(path: Path) -> str:
    digest = sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def source_workspace(root: Path) -> None:
    workspace = root / "workspaces" / "pilot"
    (workspace / "CONTEXT").mkdir(parents=True)
    (workspace / ".foundry").mkdir()
    (workspace / "workspace.yaml").write_text("schema_version: '1'\nid: workspace.pilot\n")
    (workspace / "README.md").write_text("# Pilot\n\nEvidence-backed workspace.\n")
    (workspace / "CONTEXT" / "README.md").write_text("# Context\n\nInputs and limits.\n")


def test_same_inputs_build_byte_identical_trees(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    builder = Builder(tmp_path)
    first = builder.build(builder.plan("pilot", BuildMode.draft, tmp_path / "one"))
    second = builder.build(builder.plan("pilot", BuildMode.draft, tmp_path / "two"))
    assert digest_tree(first.path) == digest_tree(second.path)
    assert "DRAFT" in (first.path / "README.md").read_text()
    manifest = json.loads((first.path / "BUILD-MANIFEST.json").read_text())
    assert "built_at" not in manifest
    assert "BUILD-MANIFEST.json" not in manifest["files"]
    assert verify_distribution(first.path).passed


def test_release_rejects_missing_release_gate(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    with pytest.raises(ValueError, match="release gate"):
        Builder(tmp_path).plan("pilot", BuildMode.release)


def test_dry_run_changes_no_bytes_and_replaces_nonempty_target(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    target = tmp_path / "out"
    target.mkdir()
    (target / "old.txt").write_text("old")
    builder = Builder(tmp_path)
    preview = builder.build(builder.plan("pilot", BuildMode.draft, target, dry_run=True))
    assert preview.changed_files and (target / "old.txt").exists()
    built = builder.build(builder.plan("pilot", BuildMode.draft, target))
    assert not (target / "old.txt").exists()
    assert verify_distribution(built.path).passed
