import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_foundry.cli.app import app

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


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_is_registered_and_supports_json_help(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--format", "json", "--help"])
    assert result.exit_code == 0, result.stdout


def test_schema_failure_maps_to_exit_3(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "--root", str(tmp_path), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == payload["exit_code"] == 3
    assert payload["diagnostics"][0]["category"] == "schema"


def test_workspace_status_is_a_noninteractive_maturity_dashboard() -> None:
    root = Path(__file__).parents[2]
    result = runner.invoke(
        app,
        [
            "workspace",
            "status",
            "--root",
            str(root),
            "--workspace",
            "harness-foundry-pilot",
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    values = set(payload["next_actions"])
    assert result.exit_code == 0
    assert "skills=1/1 validated" in values
    assert "case_coverage=boundary,failure,normal" in values
    assert "unknowns=1; unmanaged=0" in values
    assert "harness=complete" in values
    assert "readiness=conditional_ready" in values
    assert "blocking=0" in values


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
