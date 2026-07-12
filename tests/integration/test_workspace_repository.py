from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.domain.assessment import AssessmentSnapshot
from human_to_agent.domain.assets import TaskContract, WorkspaceManifest
from human_to_agent.domain.stages import Stage, assess_stage
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.workspaces import initialize

RUNNER = CliRunner()


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


def filesystem_state(root: Path) -> tuple[tuple[str, bool, bytes], ...]:
    return tuple(
        (
            path.relative_to(root).as_posix(),
            path.is_dir(),
            b"" if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    )


@pytest.mark.parametrize(
    "slug",
    (
        "../escaped",
        "nested/slug",
        "Upper",
        "has_underscore",
        "-leading",
        "trailing-",
        "double--hyphen",
        "a" * 65,
    ),
)
def test_invalid_workspace_slug_is_rejected_without_filesystem_changes(
    tmp_path: Path, slug: str
) -> None:
    initialize(tmp_path, dry_run=False)
    before = filesystem_state(tmp_path)

    result = RUNNER.invoke(
        app,
        [
            "workspace",
            "new",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--",
            slug,
        ],
    )

    assert filesystem_state(tmp_path) == before
    assert result.exit_code == 2
    assert '"code": "workspace.slug_invalid"' in result.stdout


def test_workspace_new_records_the_supplied_purpose(tmp_path: Path) -> None:
    initialize(tmp_path, dry_run=False)
    purpose = 'Review the owner\'s "quoted" goal:\nretain exact wording.'

    result = RUNNER.invoke(
        app,
        [
            "workspace",
            "new",
            "purpose-check",
            "--root",
            str(tmp_path),
            "--purpose",
            purpose,
        ],
    )

    assert result.exit_code == 0, result.stdout
    manifest = yaml.safe_load(
        (tmp_path / "workspaces/purpose-check/workspace.yaml").read_text(encoding="utf-8")
    )
    assert manifest["purpose"] == purpose


@pytest.mark.parametrize(
    ("option", "value"),
    (("--owner", ""), ("--owner", "   "), ("--purpose", ""), ("--purpose", "   ")),
)
def test_workspace_new_rejects_empty_metadata_before_writes(
    tmp_path: Path, option: str, value: str
) -> None:
    initialize(tmp_path, dry_run=False)
    before = filesystem_state(tmp_path)

    result = RUNNER.invoke(
        app,
        ["workspace", "new", "invalid-metadata", "--root", str(tmp_path), option, value],
    )

    assert result.exit_code == 2
    assert filesystem_state(tmp_path) == before
    assert not (tmp_path / "workspaces/invalid-metadata").exists()


def test_workspace_new_renders_every_manifest_entry(tmp_path: Path) -> None:
    initialize(tmp_path, dry_run=False)
    result = RUNNER.invoke(
        app,
        ["workspace", "new", "render-check", "--root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.stdout

    repository_root = Path(__file__).parents[2]
    template_manifest = yaml.safe_load(
        (repository_root / "templates/child-workspace/manifest.yaml").read_text(encoding="utf-8")
    )
    workspace = tmp_path / "workspaces/render-check"
    assert all((workspace / relative).is_dir() for relative in template_manifest["directories"])
    assert all((workspace / relative).is_file() for relative in template_manifest["templates"])
    assert all((workspace / relative).is_file() for relative in template_manifest["state_files"])


def test_new_scaffold_is_a_recorded_valid_draft_that_passes_no_stage_gate(
    tmp_path: Path,
) -> None:
    initialize(tmp_path, dry_run=False)
    purpose = "Turn supplied incident notes into a reviewed response plan."
    result = RUNNER.invoke(
        app,
        [
            "workspace",
            "new",
            "draft-check",
            "--root",
            str(tmp_path),
            "--owner",
            "incident-owner",
            "--purpose",
            purpose,
        ],
    )
    assert result.exit_code == 0, result.stdout

    workspace = tmp_path / "workspaces/draft-check"
    workspace_manifest = WorkspaceManifest.model_validate(
        yaml.safe_load((workspace / "workspace.yaml").read_text(encoding="utf-8"))
    )
    contract = TaskContract.model_validate(
        yaml.safe_load((workspace / "TASK-CONTRACT/contract.yaml").read_text(encoding="utf-8"))
    )
    stage_state = AssessmentSnapshot.model_validate(
        yaml.safe_load((workspace / "ASSESSMENTS/stage-state.yaml").read_text(encoding="utf-8"))
    )

    assert workspace_manifest.status == contract.status == "draft"
    assert workspace_manifest.purpose == contract.business_goal == purpose
    assert workspace_manifest.owner_id == contract.owner_id == "incident-owner"
    assert stage_state.facts == frozenset()
    assert stage_state.evidence == {}
    assert all(not assess_stage(stage, stage_state).passed for stage in Stage)
    assert purpose in (workspace / "README.md").read_text(encoding="utf-8")
    assert (workspace / "CHANGELOG.md").is_file()
    assert (workspace / "TASK-CONTRACT/narrative.md").is_file()

    validation = RUNNER.invoke(
        app,
        ["validate", "--root", str(tmp_path), "--workspace", "draft-check", "--format", "json"],
    )
    assert validation.exit_code == 0, validation.stdout

    snapshot = SourceRepository(tmp_path).snapshot("draft-check")
    index = ArtifactIndex.model_validate(
        yaml.safe_load(
            (workspace / ".foundry/artifact-index.yaml").read_text(encoding="utf-8")
        )
    )
    assert set(index.by_path()) == {item.path for item in snapshot.files}
