import shutil
from pathlib import Path

import yaml

from human_to_agent.services.adapters import verify_adapter_sources

ROOT = Path(__file__).parents[2]


def test_each_source_skill_has_thin_codex_and_opencode_adapter() -> None:
    names = yaml.safe_load((ROOT / "skills/catalog.yaml").read_text())["skills"]
    for name in names:
        source = ROOT / "skills" / name / "SKILL.md"
        for adapter in (
            ROOT / ".codex" / "skills" / name / "SKILL.md",
            ROOT / ".opencode" / "skills" / name / "SKILL.md",
        ):
            text = adapter.read_text()
            assert f"skills/{name}/SKILL.md" in text
            assert "hta validate" in text
            assert len(text.splitlines()) <= 20
            assert source.is_file()


def test_agent_adapters_enforce_permissions_and_resolve_sources() -> None:
    names = yaml.safe_load((ROOT / "agents/catalog.yaml").read_text())["agents"]
    for name in names:
        assert (ROOT / ".codex" / "agents" / f"{name}.toml").is_file()
        adapter = ROOT / ".opencode" / "agents" / f"{name}.md"
        text = adapter.read_text().lower()
        assert f"agents/{name}.md" in text
        if name in {"maturity-reviewer", "independent-verifier"}:
            assert "edit: deny" in text and "network: deny" in text


def test_adapter_configs_and_commands_are_discoverable() -> None:
    assert (ROOT / ".codex/config.toml").is_file()
    assert (ROOT / "opencode.json").is_file()
    assert {path.name for path in (ROOT / ".opencode/commands").glob("*.md")} == {
        "hta-workspace.md",
        "hta-review.md",
        "hta-build.md",
    }


def test_source_change_requires_adapter_recertification(tmp_path: Path) -> None:
    for relative in ("skills", ".codex", ".opencode"):
        shutil.copytree(ROOT / relative, tmp_path / relative)
    assert verify_adapter_sources(tmp_path).passed
    source = tmp_path / "skills/work-reproduction/SKILL.md"
    source.write_text(source.read_text() + "\nmaterial change\n")
    report = verify_adapter_sources(tmp_path)
    assert not report.passed
    assert report.diagnostics[0].category == "adapter"
