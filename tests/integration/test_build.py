import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.domain.builds import BuildMode, BuildPlan
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.services.build import Builder
from human_to_agent.services.distribution_verify import verify_distribution

RUNNER = CliRunner()


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
    (workspace / "AGENTS.md").write_text("# Agent guidance\n\nEvidence-backed operation.\n")
    (workspace / "README.md").write_text("# Pilot\n\nEvidence-backed workspace.\n")
    (workspace / "CONTEXT" / "README.md").write_text("# Context\n\nInputs and limits.\n")


def test_same_inputs_build_byte_identical_trees(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    builder = Builder(tmp_path)
    first = builder.build(builder.plan("pilot", BuildMode.draft, tmp_path / "one"))
    second = builder.build(builder.plan("pilot", BuildMode.draft, tmp_path / "two"))
    assert digest_tree(first.path) == digest_tree(second.path)
    assert "DRAFT" in (first.path / "README.md").read_text()
    assert (first.path / "AGENTS.md").is_file()
    manifest = json.loads((first.path / "BUILD-MANIFEST.json").read_text())
    assert "built_at" not in manifest
    assert "BUILD-MANIFEST.json" not in manifest["files"]
    assert verify_distribution(first.path).passed


def test_build_includes_untyped_data_and_assets_as_original_bytes(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    workspace = tmp_path / "workspaces/pilot"
    asset = workspace / "ASSETS/roles.yaml"
    asset.parent.mkdir()
    asset_bytes = b"roles:\n  - !custom-role\n    name: editor\n"
    asset.write_bytes(asset_bytes)
    database = workspace / "DATA/project.sqlite"
    database.parent.mkdir()
    database_bytes = b"SQLite format 3\x00fixture"
    database.write_bytes(database_bytes)

    built = Builder(tmp_path).build(
        Builder(tmp_path).plan("pilot", BuildMode.draft, tmp_path / "out")
    )
    manifest = json.loads((built.path / "BUILD-MANIFEST.json").read_text(encoding="utf-8"))

    assert (built.path / "ASSETS/roles.yaml").read_bytes() == asset_bytes
    assert (built.path / "DATA/project.sqlite").read_bytes() == database_bytes
    assert {"ASSETS/roles.yaml", "DATA/project.sqlite"} <= set(manifest["files"])
    assert verify_distribution(built.path).passed


def test_release_rejects_fake_gate_for_empty_workspace(tmp_path: Path) -> None:
    assert RUNNER.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(tmp_path)]).exit_code == 0
    gate = tmp_path / "workspaces/pilot/.foundry/release-gate.yaml"
    gate.write_text("passed: true\nreadiness: conditional_ready\n", encoding="utf-8")

    with pytest.raises(ValueError, match="current stage 5"):
        Builder(tmp_path).plan("pilot", BuildMode.release)


def test_build_rechecks_release_gate_for_a_handcrafted_plan(tmp_path: Path) -> None:
    assert RUNNER.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(tmp_path)]).exit_code == 0
    snapshot = SourceRepository(tmp_path).snapshot("pilot")
    destination = tmp_path / "forged-release"
    forged = BuildPlan(
        workspace_id="pilot",
        mode=BuildMode.release,
        destination=destination,
        source_digest=tree_digest(snapshot),
    )

    with pytest.raises(ValueError, match="release requires current stage 5"):
        Builder(tmp_path).build(forged)

    assert not destination.exists()


def test_build_renders_the_exact_snapshot_that_passed_digest_check(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    builder = Builder(tmp_path)
    destination = tmp_path / "out"
    plan = builder.plan("pilot", BuildMode.draft, destination)
    source_readme = tmp_path / "workspaces/pilot/README.md"
    delegate = builder.repository

    class MutatingRepository:
        def __init__(self) -> None:
            self.calls = 0

        def snapshot(self, slug: str):  # type: ignore[no-untyped-def]
            snapshot = delegate.snapshot(slug)
            self.calls += 1
            if self.calls == 1:
                source_readme.write_text(
                    "# Pilot\n\nContent introduced after the checked snapshot.\n",
                    encoding="utf-8",
                )
            return snapshot

    mutating = MutatingRepository()
    builder.repository = mutating  # type: ignore[assignment]

    result = builder.build(plan)

    rendered = (result.path / "README.md").read_text(encoding="utf-8")
    assert "Evidence-backed workspace." in rendered
    assert "Content introduced after the checked snapshot." not in rendered
    assert mutating.calls == 1


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


def test_build_rejects_a_destination_that_would_replace_normative_sources(
    tmp_path: Path,
) -> None:
    source_workspace(tmp_path)
    workspace = tmp_path / "workspaces/pilot"
    before = digest_tree(workspace)
    snapshot = SourceRepository(tmp_path).snapshot("pilot")
    forged = BuildPlan(
        workspace_id="pilot",
        mode=BuildMode.draft,
        destination=workspace,
        source_digest=tree_digest(snapshot),
    )

    with pytest.raises(ValueError, match="protected repository path"):
        Builder(tmp_path).build(forged)

    assert digest_tree(workspace) == before


def test_build_preserves_an_unrelated_fixed_name_backup_sibling(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    destination = tmp_path / "published"
    destination.mkdir()
    (destination / "old.txt").write_text("replace me", encoding="utf-8")
    unrelated = tmp_path / ".published.backup"
    unrelated.mkdir()
    sentinel = unrelated / "owner.txt"
    sentinel.write_text("unrelated owner data", encoding="utf-8")

    result = Builder(tmp_path).build(Builder(tmp_path).plan("pilot", BuildMode.draft, destination))

    assert result.published
    assert sentinel.read_text(encoding="utf-8") == "unrelated owner data"


def test_build_rejects_linked_destination_ancestor_before_external_writes(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external-build"
    external.mkdir()
    linked = tmp_path / "dist"
    try:
        try:
            linked.symlink_to(external, target_is_directory=True)
        except OSError as error:
            if os.name != "nt":
                pytest.skip(f"directory links are unavailable: {error}")
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(linked), str(external)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                pytest.skip(
                    f"directory links are unavailable: {completed.stderr or completed.stdout}"
                )

        with pytest.raises(ValueError, match=r"ancestors.*symlink or junction"):
            Builder(tmp_path).plan("pilot", BuildMode.draft)

        assert not tuple(external.iterdir())
    finally:
        if (
            linked.exists()
            or linked.is_symlink()
            or (hasattr(linked, "is_junction") and linked.is_junction())
        ):
            os.rmdir(linked)
        external.rmdir()


def test_distribution_rejects_unlisted_file_and_manifest_path_escape(tmp_path: Path) -> None:
    source_workspace(tmp_path)
    built = Builder(tmp_path).build(
        Builder(tmp_path).plan("pilot", BuildMode.draft, tmp_path / "out")
    )
    (built.path / "unlisted.txt").write_text("not in manifest", encoding="utf-8")
    assert not verify_distribution(built.path).passed

    escaped = tmp_path / "escaped.txt"
    escaped.write_text("outside", encoding="utf-8")
    manifest = {
        "files": {"../escaped.txt": sha256(escaped.read_bytes()).hexdigest()},
        "mode": "draft",
    }
    malicious = tmp_path / "malicious"
    malicious.mkdir()
    (malicious / "BUILD-MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = verify_distribution(malicious)
    assert not report.passed
    assert any(item.code == "distribution.path_invalid" for item in report.diagnostics)
