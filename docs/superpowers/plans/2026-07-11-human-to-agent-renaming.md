# Human to Agent Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every active Harness Foundry identity with the Human to Agent identity and prove the renamed workspace remains reproducible.

**Architecture:** Perform a breaking repository-wide identity migration: package and imports become `human_to_agent`, the executable becomes `hta`, and the reference pilot becomes `human-to-agent-pilot`. Preserve only original PR and historical design/plan documents as explicitly exempt evidence locations; regenerate all source-derived indexes and release assets.

**Tech Stack:** Python 3.11, Typer, Pydantic, YAML, pytest, Ruff, mypy, uv, Git.

## Global Constraints

- Product prose is `Human to Agent`; distribution/slug is `human-to-agent`; import package is `human_to_agent`; CLI is `hta`.
- No `hf`, `harness_foundry`, or `harness-foundry` runtime aliases remain.
- `PR/` and historical `docs/superpowers/*harness-foundry*` documents remain unmodified evidence.
- All normative pilot edits are recorded with `hta record-change` before release rebuilding.
- Run `uv run pytest -q`, Ruff, mypy, schema checking, renamed CLI validation, deterministic release build, and wheel install before completion.

---

### Task 1: Add the rename contract tests

**Files:**
- Create: `tests/contract/test_rename_contract.py`
- Modify: `tests/contract/test_cli_contract.py`
- Modify: `tests/contract/test_documentation.py`

**Interfaces:**
- Produces: executable tests for `hta`, `human_to_agent`, pilot slug, and historical-source-only old-name exemptions.

- [ ] **Step 1: Write the failing assertions**

```python
def test_active_repository_uses_human_to_agent_identity() -> None:
    assert (ROOT / "src/human_to_agent").is_dir()
    assert not (ROOT / "src/harness_foundry").exists()
    assert "hta" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/contract/test_rename_contract.py -q`

Expected: FAIL because active paths and executable still use the old identity.

- [ ] **Step 3: Add source-scan and pilot assertions**

```python
assert (ROOT / "workspaces/human-to-agent-pilot").is_dir()
assert "human-to-agent-pilot" in (ROOT / "README.md").read_text(encoding="utf-8")
```

- [ ] **Step 4: Commit test contract**

```powershell
git add tests/contract
git commit -m "test: define Human to Agent rename contract"
```

### Task 2: Rename package, imports, distribution metadata, and CLI

**Files:**
- Rename: `src/harness_foundry/` to `src/human_to_agent/`
- Modify: `pyproject.toml`, `uv.lock`, `README.md`, `AGENTS.md`, `scripts/verify_*.py`
- Modify: all Python imports and tests under `src/` and `tests/`

**Interfaces:**
- Produces: `hta` executable; `import human_to_agent`; JSON `version` result with Human to Agent text.

- [ ] **Step 1: Rename the package directory with Git**

```powershell
git mv src/harness_foundry src/human_to_agent
```

- [ ] **Step 2: Replace active Python module imports and entrypoint metadata**

```toml
[project]
name = "human-to-agent"

[project.scripts]
hta = "human_to_agent.cli.app:main"
```

- [ ] **Step 3: Update CLI strings and wheel verification**

```python
typer.echo(f"Human to Agent {__version__}")
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/contract/test_cli_contract.py tests/contract/test_cli_commands.py -q`

Expected: PASS using `hta` and `human_to_agent` only.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock src tests scripts README.md AGENTS.md
git commit -m "refactor: rename package and CLI to Human to Agent"
```

### Task 3: Rename pilot, source-derived assets, and release output

**Files:**
- Rename: `workspaces/harness-foundry-pilot/` to `workspaces/human-to-agent-pilot/`
- Rename: `examples/harness-foundry-pilot/`, `dist/harness-foundry-pilot/`, and `tests/golden/harness-foundry-pilot/`
- Modify: all pilot YAML/Markdown IDs, artifact index, event scope, examples, traceability, and release manifest.

**Interfaces:**
- Produces: valid `human-to-agent-pilot` source with `workspace.human-to-agent-pilot` identity and recorded index/event chain.

- [ ] **Step 1: Rename tracked pilot paths with Git**

```powershell
git mv workspaces/harness-foundry-pilot workspaces/human-to-agent-pilot
git mv examples/harness-foundry-pilot examples/human-to-agent-pilot
git mv dist/harness-foundry-pilot dist/human-to-agent-pilot
git mv tests/golden/harness-foundry-pilot tests/golden/human-to-agent-pilot
```

- [ ] **Step 2: Replace active pilot IDs and content**

```text
workspace.harness-foundry-pilot -> workspace.human-to-agent-pilot
harness-foundry-pilot -> human-to-agent-pilot
Harness Foundry Pilot -> Human to Agent Pilot
```

- [ ] **Step 3: Regenerate index and release**

Run:

```powershell
uv run hta record-change --workspace human-to-agent-pilot --format json
uv run hta validate --workspace human-to-agent-pilot --format json
uv run hta build --workspace human-to-agent-pilot --release
```

Expected: all commands exit 0; events verify passes; release path is `dist/human-to-agent-pilot/release`.

- [ ] **Step 4: Update golden digest test**

```python
assert digest == (ROOT / "tests/golden/human-to-agent-pilot/tree.sha256").read_text(
    encoding="utf-8"
).strip()
```

- [ ] **Step 5: Commit**

```powershell
git add workspaces examples dist tests/golden tests/e2e docs/traceability
git commit -m "refactor: rename reference pilot to Human to Agent"
```

### Task 4: Rename active prose, adapters, templates, CI, and state

**Files:**
- Modify: `README.md`, `AGENTS.md`, `skills/`, `agents/`, `.codex/`, `.opencode/`, `templates/`, `.github/workflows/ci.yml`, `state/`, active traceability documents.

**Interfaces:**
- Produces: Human to Agent copy everywhere an operator or adapter consumes active workspace content.

- [ ] **Step 1: Replace active branding and commands**

```text
Harness Foundry -> Human to Agent
harness-foundry -> human-to-agent
hf -> hta
```

- [ ] **Step 2: Preserve exempt history**

Do not edit `PR/**` or existing historical `docs/superpowers/*harness-foundry*` files. Ensure their references are labelled source/history context.

- [ ] **Step 3: Run contract and adapter tests**

Run: `uv run pytest tests/contract -q`

Expected: PASS with no active old-name occurrence outside exemption paths.

- [ ] **Step 4: Commit**

```powershell
git add README.md AGENTS.md skills agents .codex .opencode templates .github state docs
git commit -m "docs: rename active workspace identity to Human to Agent"
```

### Task 5: Full reproducibility verification

**Files:**
- Modify only if verification reveals a defect.

**Interfaces:**
- Produces: fresh CLI, release, wheel, and clean-tree evidence for the renamed workspace.

- [ ] **Step 1: Run static and test verification**

```powershell
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run python -m human_to_agent.services.schema_catalog --check schemas/v1
uv run pytest -q
```

- [ ] **Step 2: Run renamed operational verification**

```powershell
uv run hta doctor --format json
uv run hta validate --workspace human-to-agent-pilot --format json
uv run hta workspace status --workspace human-to-agent-pilot --format json
uv run hta events verify --workspace human-to-agent-pilot --format json
uv run python scripts/verify_deterministic_build.py human-to-agent-pilot
```

- [ ] **Step 3: Build and test the wheel**

```powershell
uv build --out-dir build/python-dist
uv run python scripts/verify_wheel_install.py build/python-dist
git diff --exit-code
```

- [ ] **Step 4: Commit verification fixes and confirm clean main branch**

```powershell
git status --short
```

Expected: no output.

