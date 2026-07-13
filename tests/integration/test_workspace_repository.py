import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.cli.errors import FoundryError
from human_to_agent.domain.assessment import AssessmentSnapshot
from human_to_agent.domain.assets import TaskContract, WorkspaceManifest
from human_to_agent.domain.stages import Stage, assess_stage
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services import workspaces as workspace_service
from human_to_agent.services.workspaces import initialize
from human_to_agent.validators.report import Diagnostic, ValidationReport

RUNNER = CliRunner()


def link_directory(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"directory links are unavailable: {error}")
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            pytest.skip(f"directory links are unavailable: {completed.stderr or completed.stdout}")


def unlink_directory_link(path: Path) -> None:
    if path.exists() or path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        os.rmdir(path)


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
    with pytest.raises(ValueError, match=r"single safe path component|outside workspace root"):
        SourceRepository(tmp_path).snapshot("../PR")


@pytest.mark.parametrize("slug", ("nested/slug", r"nested\slug", "C:drive"))
def test_snapshot_rejects_workspace_identifier_with_multiple_or_unsafe_components(
    tmp_path: Path, slug: str
) -> None:
    nested = tmp_path / "workspaces/nested/slug"
    nested.mkdir(parents=True)

    with pytest.raises(ValueError, match="single safe path component"):
        SourceRepository(tmp_path).snapshot(slug)


def test_repository_rejects_workspace_root_junction_outside_repository(tmp_path: Path) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external-workspaces"
    external.mkdir()
    try:
        link_directory(tmp_path / "workspaces", external)

        with pytest.raises(ValueError, match=r"workspace root|symlink|junction"):
            SourceRepository(tmp_path)
    finally:
        workspace_link = tmp_path / "workspaces"
        if workspace_link.exists() or (
            hasattr(workspace_link, "is_junction") and workspace_link.is_junction()
        ):
            os.rmdir(workspace_link)
        if external.exists():
            external.rmdir()


def test_repository_rejects_workspace_root_junction_inside_repository(tmp_path: Path) -> None:
    target = tmp_path / "real-workspaces"
    (target / "pilot").mkdir(parents=True)
    link_directory(tmp_path / "workspaces", target)

    with pytest.raises(ValueError, match=r"symlink|junction"):
        SourceRepository(tmp_path)


def test_snapshot_rejects_workspace_junction_alias_inside_workspace_root(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspaces"
    target = workspace_root / "real"
    target.mkdir(parents=True)
    (target / "workspace.yaml").write_text("id: workspace.real\n", encoding="utf-8")
    link_directory(workspace_root / "pilot", target)

    with pytest.raises(ValueError, match=r"symlink|junction"):
        SourceRepository(tmp_path).snapshot("pilot")


def test_workspace_new_rejects_linked_workspace_root_before_staging_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "human-to-agent.yaml").write_text('schema_version: "1"\n', encoding="utf-8")
    external = tmp_path.parent / f"{tmp_path.name}-external-create"
    external.mkdir()
    workspaces_link = tmp_path / "workspaces"
    link_directory(workspaces_link, external)
    staging_attempted = False

    def reject_staging(*_args: object, **_kwargs: object) -> str:
        nonlocal staging_attempted
        staging_attempted = True
        raise AssertionError("workspace staging started through a linked workspace root")

    monkeypatch.setattr(tempfile, "mkdtemp", reject_staging)
    try:
        with pytest.raises(FoundryError) as captured:
            workspace_service.create_workspace(
                tmp_path,
                "pilot",
                owner="maintainer",
                purpose="Exercise safe workspace creation.",
                dry_run=False,
            )

        assert captured.value.category == "filesystem"
        assert captured.value.code == "filesystem.unsafe_workspace_root"
        assert staging_attempted is False
        assert not tuple(external.iterdir())
    finally:
        unlink_directory_link(workspaces_link)
        external.rmdir()


def test_snapshot_rejects_symlinked_file_before_reading_external_bytes(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    external = tmp_path / "private.txt"
    external.write_bytes(b"must not be read as workspace evidence")
    linked = workspace / "linked.txt"
    try:
        linked.symlink_to(external)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match=r"symlink|junction"):
        SourceRepository(tmp_path).snapshot("pilot")


def test_snapshot_rejects_directory_link_that_resolves_outside_workspace(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    external = tmp_path / "external-evidence"
    external.mkdir()
    (external / "secret.txt").write_bytes(b"outside")
    linked = workspace / "EVIDENCE"
    link_directory(linked, external)

    with pytest.raises(ValueError, match=r"symlink|junction|outside"):
        SourceRepository(tmp_path).snapshot("pilot")


def test_snapshot_rejects_junction_even_when_target_stays_inside_workspace(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    target = workspace / "real-evidence"
    target.mkdir()
    link_directory(workspace / "EVIDENCE", target)

    with pytest.raises(ValueError, match=r"symlink|junction"):
        SourceRepository(tmp_path).snapshot("pilot")


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


@pytest.mark.parametrize("unsafe", ("../escaped", "/absolute", r"nested\windows", "C:drive"))
def test_workspace_new_rejects_unsafe_template_manifest_paths_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe: str
) -> None:
    initialize(tmp_path, dry_run=False)
    template_root = tmp_path / "malicious-child-template"
    template_root.mkdir()
    (template_root / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "template_version": "1",
                "directories": [unsafe],
                "templates": [],
                "state_files": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(workspace_service, "_child_template_root", lambda: template_root)

    with pytest.raises(FoundryError) as captured:
        workspace_service.create_workspace(
            tmp_path,
            "safe-slug",
            owner="maintainer",
            purpose="Reject unsafe template paths.",
            dry_run=False,
        )

    assert captured.value.code == "template.path_unsafe"
    assert not (tmp_path / "workspaces/safe-slug").exists()
    assert not (tmp_path / "escaped").exists()


def test_workspace_new_validates_staging_before_atomic_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    destination = tmp_path / "workspaces/invalid-staging"
    observed: dict[str, object] = {}

    def reject_staging(snapshot, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        observed["workspace_path"] = snapshot.workspace_path
        observed["destination_visible"] = destination.exists()
        return ValidationReport(
            diagnostics=(
                Diagnostic(
                    category="schema",
                    code="schema.simulated_invalid",
                    message="simulated staged validation failure",
                ),
            )
        )

    monkeypatch.setattr(workspace_service, "validate_workspace", reject_staging, raising=False)

    with pytest.raises(FoundryError, match="simulated staged validation failure"):
        workspace_service.create_workspace(
            tmp_path,
            "invalid-staging",
            owner="maintainer",
            purpose="Exercise staged validation.",
            dry_run=False,
        )

    staged_path = observed["workspace_path"]
    assert isinstance(staged_path, Path)
    assert staged_path.parent == tmp_path / "workspaces"
    assert staged_path.name.startswith(".invalid-staging.staging-")
    assert observed["destination_visible"] is False
    assert not destination.exists()
    assert not tuple((tmp_path / "workspaces").glob(".invalid-staging.staging-*"))


def test_workspace_new_cleans_staging_when_index_generation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    destination = tmp_path / "workspaces/index-failure"
    observed: dict[str, object] = {}

    def fail_index(_index):  # type: ignore[no-untyped-def]
        observed["destination_visible"] = destination.exists()
        observed["staging"] = tuple((tmp_path / "workspaces").glob(".index-failure.staging-*"))
        observed["listed_workspaces"] = workspace_service.list_workspaces(tmp_path).next_actions
        raise RuntimeError("simulated index generation failure")

    monkeypatch.setattr(workspace_service, "render_artifact_index", fail_index)

    with pytest.raises(RuntimeError, match="simulated index generation failure"):
        workspace_service.create_workspace(
            tmp_path,
            "index-failure",
            owner="maintainer",
            purpose="Exercise staged index generation.",
            dry_run=False,
        )

    assert observed["destination_visible"] is False
    assert len(observed["staging"]) == 1  # type: ignore[arg-type]
    assert observed["listed_workspaces"] == []
    assert not destination.exists()
    assert not tuple((tmp_path / "workspaces").glob(".index-failure.staging-*"))


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
        yaml.safe_load((workspace / ".foundry/artifact-index.yaml").read_text(encoding="utf-8"))
    )
    assert set(index.by_path()) == {item.path for item in snapshot.files}
