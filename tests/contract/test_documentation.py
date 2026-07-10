from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_readme_has_exact_bootstrap_and_five_stage_happy_path() -> None:
    text = (ROOT / "README.md").read_text()
    for command in (
        "uv sync --frozen --all-groups",
        "uv run hf init",
        "uv run hf workspace new",
        "uv run hf capture record",
        "uv run hf stage assess",
        "uv run hf stage advance",
        "uv run hf readiness assess",
        "uv run hf build --workspace harness-foundry-pilot --release",
    ):
        assert command in text
    assert "Draft versus release" in text and "Exit codes" in text


def test_agent_guidance_has_boundaries_and_verification() -> None:
    text = (ROOT / "AGENTS.md").read_text()
    assert "workspaces/" in text and "dist/" in text and "Human Gate" in text
    assert "uv run hf validate" in text and "uv run pytest" in text


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
