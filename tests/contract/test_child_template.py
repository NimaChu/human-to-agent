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
