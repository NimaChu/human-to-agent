import json
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.domain.builds import BuildMode
from human_to_agent.services.build import Builder
from human_to_agent.services.distribution_verify import verify_distribution

RUNNER = CliRunner()
ROOT = Path(__file__).parents[2]


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


def test_release_rejects_fake_gate_for_empty_workspace(tmp_path: Path) -> None:
    assert RUNNER.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(tmp_path)]).exit_code == 0
    gate = tmp_path / "workspaces/pilot/.foundry/release-gate.yaml"
    gate.write_text("passed: true\nreadiness: conditional_ready\n", encoding="utf-8")

    with pytest.raises(ValueError, match="current stage 5"):
        Builder(tmp_path).plan("pilot", BuildMode.release)


def test_reference_release_contains_complete_harness_surface(tmp_path: Path) -> None:
    result = Builder(ROOT).build(
        Builder(ROOT).plan("human-to-agent-pilot", BuildMode.release, tmp_path / "release")
    )
    required = {
        "workspace.yaml",
        "ASSESSMENTS/stage-state.yaml",
        "HARNESS/harness.yaml",
        "TOOLS/hta-cli/tool.yaml",
        "EVALUATORS/source-mapping/evaluator.yaml",
    }
    assert required <= {
        path.relative_to(result.path).as_posix()
        for path in result.path.rglob("*")
        if path.is_file()
    }


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
