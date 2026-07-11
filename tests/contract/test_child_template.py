from pathlib import Path

import yaml

from human_to_agent.services.build import PUBLIC_DIRECTORIES


def test_template_manifest_declares_complete_source_scaffold() -> None:
    root = Path(__file__).parents[2]
    manifest = yaml.safe_load((root / "templates/child-workspace/manifest.yaml").read_text())
    declared = set(manifest["directories"])
    assert set(PUBLIC_DIRECTORIES) <= declared
    assert {".foundry/checkpoints", "EVALUATORS"} <= declared
    assert {"README.md", "CHANGELOG.md", "workspace.yaml"} <= set(manifest["templates"])
