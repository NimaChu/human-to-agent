from pathlib import Path

import yaml

from human_to_agent.services.build import PUBLIC_DIRECTORIES


def test_template_manifest_declares_complete_source_scaffold() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load((root / "templates/child-workspace/manifest.yaml").read_text())
    declared = set(manifest["directories"])
    assert set(PUBLIC_DIRECTORIES) <= declared
    assert {
        ".foundry/checkpoints",
        "ASSESSMENTS",
        "EVALUATORS",
        "HARNESS",
        "TOOLS",
    } <= declared
    assert set(manifest["templates"]) == {
        "README.md",
        "CHANGELOG.md",
        "workspace.yaml",
        "TASK-CONTRACT/contract.yaml",
        "TASK-CONTRACT/narrative.md",
        "ASSESSMENTS/stage-state.yaml",
    }


def test_child_templates_are_included_in_the_installed_wheel() -> None:
    root = Path(__file__).parents[2]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.hatch.build.targets.wheel.force-include]" in pyproject
    assert '"templates/child-workspace" = "human_to_agent/templates/child-workspace"' in pyproject
