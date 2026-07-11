# Guided Session Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every new Human-to-Agent project conversation start with concise, one-question-at-a-time Agent guidance that leads into the existing evidence-backed child-workspace lifecycle.

**Architecture:** Keep the behavior in repository guidance and a shared method Skill, rather than adding a runtime wizard. `AGENTS.md` establishes the default entry behavior; `guided-session-onboarding` makes the behavior portable and testable; the practitioner role owns discovery after the first turn. Existing stages, Unknowns, Human Gates, transactions, and CLI commands remain unchanged.

**Tech Stack:** Markdown guidance, YAML skill catalog, thin Codex/OpenCode adapters, pytest contract tests, SHA-256 catalog digests.

## Global Constraints

- A new project conversation automatically starts guided onboarding unless the user explicitly requests a named maintenance, review, release, migration, or other existing operation.
- The agent asks one necessary question at a time and never requires the user to learn or execute `hta` commands.
- A child workspace is created only after a concrete goal plus a real input, example, or decision context are available.
- Missing facts are recorded as Unknowns; direct evidence, stage gates, Human Gates, transaction recording, and event integrity remain mandatory.
- The policy is for coding-Agent collaboration, not an interactive runtime UI or a new CLI command.

---

### Task 1: Establish default conversational onboarding in repository guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `agents/practitioner-guide.md`
- Modify: `README.md`
- Modify: `tests/contract/test_documentation.py`

**Interfaces:**
- Consumes: existing project-level agent guidance and `practitioner-guide` role.
- Produces: a repository-wide rule that any new project conversation starts with orientation and a single next question.

- [ ] **Step 1: Write failing documentation contract tests**

Add these assertions to `tests/contract/test_documentation.py`:

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
uv run pytest tests/contract/test_documentation.py -q
```

Expected: the two new tests fail because current guidance has no default new-session policy or conversational README entrypoint.

- [ ] **Step 3: Add the minimal guidance and role behavior**

Append this policy block to `AGENTS.md`:

```markdown
## New project conversations

- In every new project conversation, begin with a concise explanation that Human-to-Agent turns a real task into an evidence-backed child workspace and that the user does not need to know commands or templates.
- If the user has not stated a credible task goal, end the first response by asking what result they want to achieve. If they have stated a goal, acknowledge it and ask only the highest-value missing real input, example, or decision context.
- Ask one necessary question at a time. Do not require the user to run `hta` commands or complete a form; manage permitted workspace mechanics on their behalf.
- Do not create a child workspace for a greeting or ambiguous curiosity. Create it only after a concrete goal plus a real input, example, or decision context; state the derived slug before creating it.
- Do not enter this discovery protocol when the user explicitly requests a named maintenance, review, release, migration, or other existing operation.
```

Replace `agents/practitioner-guide.md` with a role description that explicitly owns the six discovery states `orientation`, `goal`, `real_case`, `constraints`, `review`, and `workspace_active`, preserves direct-evidence and Unknown requirements, and directs the role to hand source writes to the asset maintainer.

Add a `## Start a conversation` section before `## Bootstrap` in `README.md` containing:

```markdown
Open a new project conversation and speak naturally: describe the result you want or share the material you already have. The Agent introduces Human-to-Agent once, asks one question at a time, and manages permitted workspace commands. You do not need to know commands, templates, or the directory layout.
```

- [ ] **Step 4: Run the documentation contract tests and format checks**

Run:

```powershell
uv run pytest tests/contract/test_documentation.py -q
uv run ruff check tests/contract/test_documentation.py
```

Expected: all documentation contract tests pass and Ruff reports no findings.

- [ ] **Step 5: Commit the guidance deliverable**

```powershell
git add AGENTS.md agents/practitioner-guide.md README.md tests/contract/test_documentation.py
git commit -m "feat: guide new project conversations"
```

### Task 2: Add a portable guided-session shared Skill and adapters

**Files:**
- Create: `skills/guided-session-onboarding/SKILL.md`
- Modify: `skills/catalog.yaml`
- Create: `.codex/skills/guided-session-onboarding/SKILL.md`
- Create: `.opencode/skills/guided-session-onboarding/SKILL.md`
- Modify: `tests/contract/test_method_assets.py`
- Modify: `tests/contract/test_tool_adapters.py`

**Interfaces:**
- Consumes: `skills/_shared/method-contract.md`, `AGENTS.md`, and the existing adapter contract.
- Produces: a cataloged shared Skill that Codex and OpenCode can discover without duplicating business rules.

- [ ] **Step 1: Write failing method and adapter contract tests**

Add `"guided-session-onboarding"` to `REQUIRED` in `tests/contract/test_method_assets.py`. Add this test:

```python
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
    assert "one necessary question" in text
    assert "unknown" in text
    assert "explicitly requests" in text
    assert "concrete goal" in text and "real input" in text
```

The existing `test_each_source_skill_has_thin_codex_and_opencode_adapter` will fail until both adapters exist because it iterates over the catalog.

- [ ] **Step 2: Run the focused contracts and verify they fail**

Run:

```powershell
uv run pytest tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py -q
```

Expected: failure because the new Skill and both adapters do not exist and the catalog lacks the new entry.

- [ ] **Step 3: Create the shared Skill with the standard method contract**

Create `skills/guided-session-onboarding/SKILL.md` with frontmatter:

```yaml
---
name: guided-session-onboarding
description: Start every new project conversation with one-question evidence-first guidance and safely enter a real child workspace.
---
```

Include every required shared-method heading. Its procedure must define the six named states; its Unknown section must classify missing facts as Unknowns rather than inferred rules; its Human-gate section must retain stops for external or irreversible actions; its evaluator section must require a concrete goal plus real input, example, or decision context before workspace creation; and its verification section must require `hta validate` and `hta diff` before `hta record-change`.

Create both adapters with the existing thin-adapter template:

```markdown
---
name: guided-session-onboarding
description: Start every new project conversation with one-question evidence-first guidance and safely enter a real child workspace.
---

Source: `../../../skills/guided-session-onboarding/SKILL.md`

Permission: obey the source method, repository AGENTS.md, and Human Gates.
Discovery: use this adapter only to locate the shared method; it contains no business rules.
Invocation: run `uv run hta validate --workspace <id> --format json` before recording any source change.
```

Add `guided-session-onboarding` to `skills/catalog.yaml` under `skills`. Recalculate every `source_digests` value from the current bytes of every cataloged `SKILL.md`, including the new skill.

- [ ] **Step 4: Run focused contracts and adapter integrity verification**

Run:

```powershell
uv run pytest tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py -q
uv run hta doctor --format json
```

Expected: all method and adapter tests pass; doctor reports no adapter recertification requirement.

- [ ] **Step 5: Commit the portable-skill deliverable**

```powershell
git add skills .codex/skills/guided-session-onboarding .opencode/skills/guided-session-onboarding tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py
git commit -m "feat: add guided session onboarding skill"
```

### Task 3: Verify continuity with the existing lifecycle and publish

**Files:**
- Modify: `docs/traceability/completion-audit.md` only if a pre-existing claim changes; otherwise no source change.
- Verify: `AGENTS.md`, `agents/practitioner-guide.md`, `skills/guided-session-onboarding/SKILL.md`, `skills/catalog.yaml`, both adapters, and all existing tests.

**Interfaces:**
- Consumes: the completed guidance and portable-skill deliverables.
- Produces: evidence that guided onboarding does not bypass existing gates, Unknowns, validation, transaction recording, or adapters.

- [ ] **Step 1: Run targeted continuity checks**

Run:

```powershell
uv run pytest tests/contract/test_documentation.py tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py -q
uv run hta validate --workspace human-to-agent-pilot --format json
uv run hta events verify --workspace human-to-agent-pilot --format json
```

Expected: all contract tests pass; the reference pilot validates; its event chain is valid.

- [ ] **Step 2: Run the complete quality gate**

Run:

```powershell
uv run pytest -q
uv run ruff check .
uv run mypy src tests
uv run python -m human_to_agent.services.schema_catalog --check schemas/v1
git diff --check
```

Expected: all tests pass, lint and type checks report no issues, schemas match committed files, and Git reports no whitespace errors.

- [ ] **Step 3: Confirm no uncommitted verification changes remain**

Run:

```powershell
git status --short
```

Expected: no output. If a verification command changed a source file, correct the failure through its owning task, rerun the complete quality gate, and commit that task-specific correction before pushing.

- [ ] **Step 4: Push the approved commits**

Run:

```powershell
git push origin main
```

Expected: `main` on GitHub contains the guidance, shared Skill, adapters, and passing contract coverage.
