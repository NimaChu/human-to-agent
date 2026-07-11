# Conversational Harness Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the executable gaps between natural conversation, durable evidence capture, evidence-computed stages, and a transferable Agent Harness release.

**Architecture:** Repository guidance routes natural conversation while existing CLI services perform every mutation. A normative `AssessmentSnapshot` maps facts to real asset IDs; services derive mechanical facts and call the existing domain stage engine. Workspace creation, capture, stage changes, and release remain deterministic, transactional, and Unknown-aware.

**Tech Stack:** Python 3.11, Typer, Pydantic v2, YAML, Jinja2 templates, WAL transactions, hash-chained events, pytest, Ruff, mypy.

## Global Constraints

- Users provide only natural-language facts, decisions, and files; the Agent performs all workspace commands and edits.
- Missing or conflicting facts become Unknowns and are never invented as evidence.
- Workspace slugs match `^[a-z0-9]+(?:-[a-z0-9]+)*$`, maximum 64 characters, before any write.
- Handwritten `.foundry` pass flags have no stage or release authority.
- Stage and release decisions use recorded normative assets and the existing domain assessment functions.
- External and irreversible actions remain unexecuted and Human-Gated.
- The user owns final real-chat acceptance; automated tests own architecture, safety, and deterministic behavior.

---

### Task 1: Make guided onboarding internally consistent

**Files:**
- Modify: `AGENTS.md`
- Modify: `agents/practitioner-guide.md`
- Modify: `skills/_shared/method-contract.md`
- Modify: `skills/guided-session-onboarding/SKILL.md`
- Modify: `skills/catalog.yaml`
- Modify: `tests/contract/test_documentation.py`
- Modify: `tests/contract/test_method_assets.py`

**Deliverable:** Routing uses “at most one necessary question,” skips already-known states, mandates canonical creation/capture, and materializes every provisional Unknown after activation.

- [ ] Write contract tests for fast-path routing, canonical `hta workspace new`, durable capture, and pre-workspace Unknown materialization.
- [ ] Run the focused contracts and observe failures against the current prose.
- [ ] Update guidance, practitioner role, shared method contract, and onboarding Skill with the exact routing and handoff behavior.
- [ ] Recalculate the shared Skill digest and run documentation, method, and adapter tests.
- [ ] Commit with `fix: align guided onboarding handoff`.

### Task 2: Create a safe canonical child scaffold

**Files:**
- Modify: `src/human_to_agent/services/workspaces.py`
- Modify: `src/human_to_agent/cli/app.py`
- Modify: `templates/child-workspace/manifest.yaml`
- Modify: `templates/child-workspace/workspace.yaml.j2`
- Modify: `templates/child-workspace/TASK-CONTRACT/contract.yaml.j2`
- Create: `templates/child-workspace/ASSESSMENTS/stage-state.yaml.j2`
- Modify: `templates/child-workspace/README.md.j2`
- Modify: `tests/integration/test_workspace_repository.py`
- Modify: `tests/contract/test_child_template.py`

**Deliverable:** `hta workspace new <slug> --purpose <goal>` validates the slug before writes, renders a schema-valid draft scaffold and an empty assessment state, includes all Harness directories, and records the initial artifact index.

- [ ] Add failing tests for traversal/invalid slugs, no outside writes, rendered entry files, supplied purpose, and immediate validation.
- [ ] Run the focused tests and observe the unsafe/empty-scaffold failures.
- [ ] Implement pre-write slug validation and manifest-driven rendering using `render_template`.
- [ ] Make the initial templates schema-valid drafts whose placeholders carry no evidence or gate facts.
- [ ] Run workspace, template, validation, CLI, and dry-run tests.
- [ ] Commit with `feat: render safe child workspaces`.

### Task 3: Persist supplied text and files atomically

**Files:**
- Modify: `src/human_to_agent/services/asset_writer.py`
- Modify: `src/human_to_agent/services/capture.py`
- Modify: `src/human_to_agent/cli/app.py`
- Modify: `tests/integration/test_capture_unknown_commands.py`
- Modify: `tests/integration/test_transactions.py`

**Deliverable:** `capture record` accepts exactly one of `--input` and `--text`, writes content-addressed source bytes plus Evidence YAML in one transaction/event, and never stores an absolute source dependency.

- [ ] Add failing tests for text capture, file survival after source deletion, mutual exclusivity, one event, rollback, relative locator, and indexed raw bytes.
- [ ] Run the focused tests and observe failures.
- [ ] Generalize the asset writer to validate and atomically commit multiple normative files plus the index.
- [ ] Implement content-addressed file/text capture through the multi-asset writer.
- [ ] Run capture, transaction, recovery, event, and CLI contract tests.
- [ ] Commit with `feat: persist conversational evidence`.

### Task 4: Connect normative assessment state to the domain gate engine

**Files:**
- Create: `src/human_to_agent/services/assessment_state.py`
- Modify: `src/human_to_agent/validators/workspace.py`
- Modify: `src/human_to_agent/services/status_views.py`
- Modify: `src/human_to_agent/services/stage_transitions.py`
- Modify: `src/human_to_agent/services/workspaces.py`
- Modify: `src/human_to_agent/services/schema_catalog.py` only if path registration requires it
- Create: `tests/integration/test_assessment_state.py`
- Modify: `tests/e2e/test_reference_pilot.py`
- Modify: `tests/integration/test_human_gates.py`

**Deliverable:** Stage assessment and transitions load `ASSESSMENTS/stage-state.yaml`, validate real evidence IDs, derive cases/Skills/Readiness/Unknown state, call `assess_stage`, reject unrecorded changes, and update manifest plus assessment state atomically.

- [ ] Add failing tests proving fake `.foundry` gates and fake evidence IDs cannot advance, unmanaged Unknowns remove managed facts, and valid evidence-backed state can advance.
- [ ] Run focused tests and observe the bypass failures.
- [ ] Register and validate the normative assessment path and all evidence references.
- [ ] Implement derived mechanical facts and conservative Readiness validation.
- [ ] Replace gate-file reads with `assess_stage`/`assess_complete_release` calls.
- [ ] Make advance/reopen transactional across manifest, assessment state, index, and event.
- [ ] Run stage, Unknown, validation, recovery, and reference Pilot tests.
- [ ] Commit with `fix: compute stage gates from evidence`.

### Task 5: Recompute release gates and publish the complete Harness

**Files:**
- Modify: `src/human_to_agent/services/build.py`
- Modify: `src/human_to_agent/services/distribution_verify.py`
- Modify: `templates/child-workspace/manifest.yaml`
- Create: `workspaces/human-to-agent-pilot/ASSESSMENTS/stage-state.yaml`
- Modify: `workspaces/human-to-agent-pilot/.foundry/artifact-index.yaml`
- Modify: `workspaces/human-to-agent-pilot/.foundry/events.jsonl`
- Modify: `dist/human-to-agent-pilot/release/**`
- Modify: `tests/integration/test_build.py`
- Modify: `tests/e2e/test_reference_pilot.py`
- Modify: `tests/contract/test_child_template.py`
- Modify: `tests/golden/human-to-agent-pilot/tree.sha256`

**Deliverable:** Release ignores handwritten flags, recomputes complete-release readiness from recorded normative evidence, blocks unmanaged Unknowns, and includes workspace, assessment, Harness, Tool, and Evaluator assets.

- [ ] Add failing tests that an empty workspace with fake release flag is rejected and the Pilot release contains all executable Harness assets.
- [ ] Run focused build tests and observe the bypass and packaging failures.
- [ ] Replace release-flag trust with computed assessment and recorded-index checks.
- [ ] Expand public directories and standalone distribution verification.
- [ ] Add an evidence-mapped Pilot assessment state, record it through `hta record-change`, rebuild the release, and update the deterministic golden digest.
- [ ] Run build, deterministic, distribution, Pilot, event-chain, and validation tests.
- [ ] Commit with `fix: gate complete harness releases`.

### Task 6: Complete branch verification

**Files:**
- Verify all changed files and generated schemas/releases.

**Deliverable:** The branch has no open Critical/Important review finding and passes every automated project gate.

- [ ] Run `uv run pytest -q`.
- [ ] Run `uv run ruff format --check .` and `uv run ruff check .`.
- [ ] Run `uv run mypy src tests`.
- [ ] Run `uv run python -m human_to_agent.services.schema_catalog --check schemas/v1`.
- [ ] Run `uv run hta doctor --format json`, Pilot validation, event verification, and deterministic release verification.
- [ ] Run `git diff --check` and whole-branch review.
- [ ] Fix and re-review every Critical or Important finding before branch integration.
