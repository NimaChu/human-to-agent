import re
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).parents[2]
REQUIRED = {
    "work-reproduction",
    "task-contract",
    "unknown-evidence",
    "skill-candidates",
    "case-evaluation",
    "harness-composition",
    "stage-review",
    "loop-readiness",
    "deviation-log",
    "independent-reproduction",
    "workspace-maintenance",
    "guided-session-onboarding",
}
SECTIONS = {
    "# Outcome",
    "# Inputs",
    "# Preconditions",
    "# Applies when",
    "# Does not apply when",
    "# Dependencies",
    "# Source-of-truth files",
    "# Procedure",
    "# Unknown handling",
    "# Human gates and stop conditions",
    "# Evaluator and acceptance",
    "# Error semantics",
    "# Evidence written",
    "# Verification commands",
}


def frontmatter(text: str) -> dict[str, str]:
    return cast(dict[str, str], yaml.safe_load(text.split("---", 2)[1]))


def test_all_method_skills_follow_contract() -> None:
    catalog = yaml.safe_load((ROOT / "skills/catalog.yaml").read_text())
    assert set(catalog["skills"]) == REQUIRED
    for name in REQUIRED:
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        metadata = frontmatter(text)
        assert metadata["name"] == name
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        assert 20 <= len(metadata["description"]) <= 240
        assert {line for line in text.splitlines() if line.startswith("# ")} >= SECTIONS
        assert "hta validate" in text and "evidence" in text.lower()


def test_unknown_skill_contains_all_discovery_cards() -> None:
    text = (ROOT / "skills/unknown-evidence/SKILL.md").read_text().lower()
    cards = (
        "four-quadrant inventory",
        "blindspot pass",
        "vocabulary teaching",
        "contrasting design directions",
        "intervention brainstorming",
        "blast-radius interview",
        "reference semantics map",
        "tweakable plan",
        "implementation deviation log",
        "buy-in artifact",
        "understanding quiz",
    )
    assert all(card in text for card in cards)


def test_guided_session_skill_defines_safe_discovery_protocol() -> None:
    text = (ROOT / "skills/guided-session-onboarding/SKILL.md").read_text().lower()
    for state in (
        "orientation",
        "goal",
        "real_case",
        "constraints",
        "review",
        "workspace_active",
    ):
        assert state in text
    assert "at most one necessary question" in text
    assert "unknown" in text
    assert "explicitly requests" in text
    assert "concrete goal" in text and "real input" in text


def test_guided_session_contract_defines_fast_path_and_canonical_handoff() -> None:
    for relative in (
        "skills/_shared/method-contract.md",
        "skills/guided-session-onboarding/SKILL.md",
    ):
        text = (ROOT / relative).read_text().lower()
        assert "skip already-known states" in text
        assert "without manufacturing another question" in text
        assert "`hta workspace new`" in text
        assert "`hta capture record`" in text
        assert "every provisional unknown" in text
        assert "normative" in text


def test_agents_are_separated_and_verifier_is_read_only() -> None:
    catalog = yaml.safe_load((ROOT / "agents/catalog.yaml").read_text())
    assert set(catalog["agents"]) == {
        "practitioner-guide",
        "asset-maintainer",
        "maturity-reviewer",
        "independent-verifier",
    }
    verifier = (ROOT / "agents/independent-verifier.md").read_text().lower()
    maintainer = (ROOT / "agents/asset-maintainer.md").read_text().lower()
    assert "read-only" in verifier and "must not edit normative sources" in verifier
    assert verifier != maintainer
    method_text = "\n".join(
        path.read_text().lower()
        for folder in (ROOT / "skills", ROOT / "agents", ROOT / ".codex", ROOT / ".opencode")
        for path in folder.rglob("*")
        if path.is_file()
    )
    assert "acme" not in method_text
