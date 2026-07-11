from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_readme_has_exact_bootstrap_and_five_stage_happy_path() -> None:
    text = (ROOT / "README.md").read_text()
    for command in (
        "uv sync --frozen --all-groups",
        "uv run hta init",
        "uv run hta workspace new",
        "uv run hta capture record",
        "uv run hta stage assess",
        "uv run hta stage advance",
        "uv run hta readiness assess",
        "uv run hta build --workspace human-to-agent-pilot --release",
    ):
        assert command in text
    assert "Draft versus release" in text and "Exit codes" in text


def test_agent_guidance_has_boundaries_and_verification() -> None:
    text = (ROOT / "AGENTS.md").read_text()
    assert "workspaces/" in text and "dist/" in text and "Human Gate" in text
    assert "uv run hta validate" in text and "uv run pytest" in text


def test_agent_guidance_defaults_new_sessions_to_guided_onboarding() -> None:
    text = (ROOT / "AGENTS.md").read_text().lower()
    assert "new project conversation" in text
    assert "one necessary question" in text
    assert "do not require the user to run" in text
    assert "explicitly requests" in text


def test_readme_explains_conversational_entrypoint() -> None:
    text = (ROOT / "README.md").read_text().lower()
    assert "start a conversation" in text
    assert "one question at a time" in text
    assert "do not need to know commands" in text


def test_runbooks_cover_failure_states() -> None:
    expected = {
        "docs/operations/recovery.md": ("prepared", "event_committed", "all-old", "all-new"),
        "docs/operations/migration.md": ("dry-run", "candidate", "rollback", "event"),
        "docs/operations/recertification.md": ("version vector", "stage4", "readiness", "blocking"),
    }
    for relative, terms in expected.items():
        text = (ROOT / relative).read_text().lower()
        assert all(term.lower() in text for term in terms)


def test_ci_has_required_cross_platform_matrix_and_steps() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "ubuntu-latest" in text and "windows-latest" in text
    assert 'python-version: ["3.11", "3.12"]' in text
    assert "actions/checkout@v4" in text and "astral-sh/setup-uv@v6" in text
    for command in (
        "ruff format --check",
        "mypy src tests",
        "schema_catalog --check",
        "verify_wheel_install.py",
    ):
        assert command in text
