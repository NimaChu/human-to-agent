from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_required_root_layout_exists() -> None:
    required = {
        "README.md",
        "AGENTS.md",
        "foundry.yaml",
        "pyproject.toml",
        "PR",
        "docs",
        "state",
        "workspaces",
    }
    assert required <= {path.name for path in ROOT.iterdir()}


def test_runtime_dependencies_are_offline_safe() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "requests" not in text
    assert "httpx" not in text
    assert 'requires-python = ">=3.11"' in text
