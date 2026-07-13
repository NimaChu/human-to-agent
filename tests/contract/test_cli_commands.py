import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.services.workspaces import create_workspace, initialize

runner = CliRunner()
COMMANDS = (
    ("init",),
    ("workspace", "new"),
    ("workspace", "list"),
    ("workspace", "status"),
    ("capture", "record"),
    ("unknown", "add"),
    ("unknown", "update"),
    ("unknown", "close"),
    ("unknown", "reopen"),
    ("validate",),
    ("stage", "assess"),
    ("stage", "advance"),
    ("stage", "reopen"),
    ("readiness", "assess"),
    ("diff",),
    ("record-change",),
    ("migrate",),
    ("events", "verify"),
    ("events", "replay"),
    ("doctor",),
    ("build",),
)


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


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_is_registered_and_supports_json_help(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--format", "json", "--help"])
    assert result.exit_code == 0, result.stdout


def test_schema_failure_maps_to_exit_3(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "--root", str(tmp_path), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == payload["exit_code"] == 3
    assert payload["diagnostics"][0]["category"] == "schema"


def test_workspace_status_rejects_linked_workspace_before_reading_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    external = tmp_path / "external-workspace"
    external.mkdir()
    manifest = external / "workspace.yaml"
    manifest.write_text("external: true\n", encoding="utf-8")
    linked = tmp_path / "workspaces/pilot"
    link_directory(linked, external)
    original_read_text = Path.read_text

    def reject_external_read(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("workspace status read a linked external manifest")
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", reject_external_read)
    try:
        result = runner.invoke(
            app,
            ["workspace", "status", "--root", str(tmp_path), "-w", "pilot", "--format", "json"],
        )

        payload = json.loads(result.stdout)
        assert result.exit_code == payload["exit_code"] == 8
        assert payload["diagnostics"][0]["category"] == "filesystem"
        assert payload["diagnostics"][0]["code"] == "filesystem.unsafe_workspace_path"
    finally:
        unlink_directory_link(linked)


def test_workspace_status_rejects_linked_asset_directory_before_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    create_workspace(
        tmp_path,
        "pilot",
        owner="maintainer",
        purpose="Exercise safe status reads.",
        dry_run=False,
    )
    skills = tmp_path / "workspaces/pilot/SKILLS"
    skills.rmdir()
    external = tmp_path / "external-skills"
    external.mkdir()
    external_skill = external / "secret.yaml"
    external_skill.write_text("status: validated\n", encoding="utf-8")
    link_directory(skills, external)
    original_read_text = Path.read_text

    def reject_external_read(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("workspace status read a linked external asset")
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", reject_external_read)
    try:
        result = runner.invoke(
            app,
            ["workspace", "status", "--root", str(tmp_path), "-w", "pilot", "--format", "json"],
        )

        payload = json.loads(result.stdout)
        assert result.exit_code == payload["exit_code"] == 8
        assert payload["diagnostics"][0]["category"] == "filesystem"
        assert payload["diagnostics"][0]["code"] == "filesystem.unsafe_workspace_path"
    finally:
        unlink_directory_link(skills)


def test_unknown_operation_rejects_linked_unknown_directory_before_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    create_workspace(
        tmp_path,
        "pilot",
        owner="maintainer",
        purpose="Exercise safe Unknown reads.",
        dry_run=False,
    )
    added = runner.invoke(
        app,
        ["unknown", "add", "--root", str(tmp_path), "-w", "pilot", "--title", "Owner"],
    )
    assert added.exit_code == 0, added.stdout
    unknowns = tmp_path / "workspaces/pilot/UNKNOWNS"
    unknown_path = next(unknowns.glob("*.yaml"))
    unknown_id = str(yaml.safe_load(unknown_path.read_text(encoding="utf-8"))["id"])
    external = tmp_path / "external-unknowns"
    shutil.copytree(unknowns, external)
    shutil.rmtree(unknowns)
    link_directory(unknowns, external)
    original_read_text = Path.read_text

    def reject_external_read(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("Unknown operation read through a linked directory")
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", reject_external_read)
    try:
        result = runner.invoke(
            app,
            [
                "unknown",
                "reopen",
                "--root",
                str(tmp_path),
                "-w",
                "pilot",
                "--id",
                unknown_id,
                "--evidence",
                "evidence.missing",
                "--reason",
                "Contradiction",
                "--format",
                "json",
            ],
        )

        payload = json.loads(result.stdout)
        assert result.exit_code == payload["exit_code"] == 8
        assert payload["diagnostics"][0]["code"] == "unknown.path_unsafe"
    finally:
        unlink_directory_link(unknowns)


def test_events_verify_rejects_linked_foundry_before_reading_event_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize(tmp_path, dry_run=False)
    create_workspace(
        tmp_path,
        "pilot",
        owner="maintainer",
        purpose="Exercise safe event reads.",
        dry_run=False,
    )
    foundry = tmp_path / "workspaces/pilot/.foundry"
    shutil.rmtree(foundry)
    external = tmp_path / "external-foundry"
    external.mkdir()
    (external / "events.jsonl").write_text('{"external": true}\n', encoding="utf-8")
    link_directory(foundry, external)
    original_read_bytes = Path.read_bytes

    def reject_external_read(path: Path) -> bytes:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("events verify read through a linked .foundry directory")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_external_read)
    try:
        result = runner.invoke(
            app,
            ["events", "verify", "--root", str(tmp_path), "-w", "pilot", "--format", "json"],
        )

        payload = json.loads(result.stdout)
        assert result.exit_code == payload["exit_code"] == 8
        assert payload["diagnostics"][0]["code"] == "event.path_unsafe"
    finally:
        unlink_directory_link(foundry)


def test_workspace_list_rejects_linked_workspaces_root(tmp_path: Path) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external-list"
    (external / "pilot").mkdir(parents=True)
    workspaces_link = tmp_path / "workspaces"
    link_directory(workspaces_link, external)
    try:
        result = runner.invoke(
            app, ["workspace", "list", "--root", str(tmp_path), "--format", "json"]
        )

        payload = json.loads(result.stdout)
        assert result.exit_code == payload["exit_code"] == 8
        assert payload["diagnostics"][0]["code"] == "filesystem.unsafe_workspace_root"
    finally:
        unlink_directory_link(workspaces_link)
        (external / "pilot").rmdir()
        external.rmdir()


def test_workspace_list_ignores_hidden_staging_directories(tmp_path: Path) -> None:
    (tmp_path / "workspaces/.pilot.staging-interrupted").mkdir(parents=True)

    result = runner.invoke(app, ["workspace", "list", "--root", str(tmp_path), "--format", "json"])

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["next_actions"] == []


@pytest.mark.parametrize(
    "command",
    (
        ("init",),
        ("workspace", "new"),
        ("capture", "record"),
        ("unknown", "add"),
        ("unknown", "update"),
        ("unknown", "close"),
        ("unknown", "reopen"),
        ("stage", "advance"),
        ("stage", "reopen"),
        ("record-change",),
        ("migrate",),
        ("build",),
    ),
)
def test_state_changing_commands_accept_dry_run(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--format", "json", "--dry-run", "--help"])
    assert result.exit_code == 0, result.stdout
