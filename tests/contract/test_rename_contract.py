import json
from pathlib import Path

from typer.testing import CliRunner

from human_to_agent.cli.app import app

ROOT = Path(__file__).parents[2]
runner = CliRunner()


def test_active_workspace_identity_uses_human_to_agent() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert (ROOT / "src/human_to_agent").is_dir()
    assert not (ROOT / "src/harness_foundry").exists()
    assert 'name = "human-to-agent"' in pyproject
    assert 'hta = "human_to_agent.cli.app:main"' in pyproject
    assert "Human to Agent" in readme
    assert "Harness Foundry" not in readme


def test_hta_cli_and_renamed_reference_pilot_are_operational() -> None:
    result = runner.invoke(app, ["version", "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["command"] == "version"
    assert (ROOT / "workspaces/human-to-agent-pilot").is_dir()
    assert (ROOT / "dist/human-to-agent-pilot/release/BUILD-MANIFEST.json").is_file()
