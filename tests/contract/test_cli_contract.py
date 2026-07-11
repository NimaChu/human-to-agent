import json

from typer.testing import CliRunner

from human_to_agent.cli.app import app

runner = CliRunner()


def test_version_uses_stable_json_envelope() -> None:
    result = runner.invoke(app, ["version", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "changed_files": [],
        "command": "version",
        "diagnostics": [],
        "exit_code": 0,
        "next_actions": [],
        "status": "ok",
    }


def test_invalid_format_is_usage_error() -> None:
    result = runner.invoke(app, ["version", "--format", "xml"])
    assert result.exit_code == 2
