# Human to Agent

Turn work you currently do by hand into a reusable Agent workspace—by talking naturally and sharing the real files or examples you already have.

You do not need to know commands, fill in templates, or organize the repository yourself. You also do not need to write a special prompt. Start a new conversation in this project and explain what you are trying to accomplish. The Agent guides you one question at a time and handles the workspace operations for you.

## What this project does

Human to Agent helps an Agent turn an existing piece of work into a reliable, transferable harness:

1. Understands the result you want and inspects the material you provide.
2. Saves original inputs as traceable evidence instead of inventing missing facts.
3. Records unclear, conflicting, or unverified information as explicit Unknowns.
4. Distills the work into instructions, cases, checks, policies, state, tools, and Human Gates.
5. Tests whether another Agent can reproduce the work and evaluates how much autonomy is safe.
6. Builds a self-contained child workspace that can be reviewed, versioned, and reused.

In short: **bring a real task; leave with an evidence-backed Agent harness.**

## Start a conversation

Open a new project conversation and describe the work in your own words. For example:

> I prepare this report every week. Here are last week's source files and final report.

or:

> I want an Agent to review these requirements the same way our team does.

The Agent briefly introduces the process, identifies the most useful next piece of information, and does the repository work on your behalf. Attach files, examples, rules, or past outputs as they become relevant.

## What you get

Each real task becomes a child workspace under `workspaces/` containing the evidence, Task Contract, Unknowns, Skills, test cases, evaluators, workflow, policies, Human Gates, state model, and readiness decision needed to operate it responsibly.

The authoritative business record is the Markdown, YAML, and JSONL under `workspaces/`. Generated releases under `dist/` are outputs only and are never treated as source evidence.

## Current scope

- Conversation-first and file-first; there is no interactive UI yet.
- The Agent may manage local workspace operations for the user.
- External or irreversible actions are not executed directly. The workspace can prepare an action package, but a Human Gate must approve, reject, or modify it.
- Readiness may recommend an autonomy ceiling, but only direct owner evidence can approve an autonomy level.

## Bootstrap

```powershell
python -m pip install uv
uv sync --frozen --all-groups
uv run hta version --format json
uv run hta init
```

## Agent-operated lifecycle reference

Users do not need to run these commands. They are the deterministic operations the Agent performs behind the conversation; maintainers may use them directly for diagnosis or recovery. Replace `<workspace>` with the child-workspace slug when operating manually.

```powershell
uv run hta workspace new <workspace>
uv run hta capture record --workspace <workspace>
uv run hta unknown add --workspace <workspace>
uv run hta stage assess --workspace <workspace>
uv run hta stage advance --workspace <workspace>
# Repeat assess/advance through stages 2-5 after recording direct gate evidence.
uv run hta readiness assess --workspace <workspace>
uv run hta validate --workspace <workspace> --format json
uv run hta record-change --workspace <workspace>
uv run hta build --workspace <workspace> --draft
```

The supplied real pilot is already release-gated:

```powershell
uv run hta validate --workspace human-to-agent-pilot --format json
uv run hta events verify --workspace human-to-agent-pilot --format json
uv run hta build --workspace human-to-agent-pilot --release
```

## Draft versus release

Draft builds are allowed at any stage and contain a visible `DRAFT` warning. Release builds require a passing computed complete-release assessment, at least conditional Readiness, an explicit evidence-backed autonomy approval, no unmanaged Unknown, and an artifact index matching every normative source byte. Readiness recommends a ceiling but never acts as owner approval. `BUILD-MANIFEST.json` contains deterministic versions, source digest, and per-file digests—never a clock or random ID. Handwritten `.foundry` gate flags have no release authority.

The first release has no interactive UI and does not execute external or irreversible actions. It can prepare an action package; a Human Gate records approve, reject, or modify, while a separate executor remains out of scope.

## Operations

- Architecture: `docs/architecture/overview.md`
- Five stages: `docs/methodology/five-stages.md`
- Crash recovery: `docs/operations/recovery.md`
- Schema migration: `docs/operations/migration.md`
- Change re-certification: `docs/operations/recertification.md`
- Requirement proof: `docs/traceability/completion-audit.md`

Run `uv run hta doctor --format json` for configuration, secret, transaction, event, and adapter checks. `hta events verify` detects truncation, sequence gaps, predecessor mismatch, and payload tampering.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 2 | Usage or root configuration |
| 3 | Schema |
| 4 | Reference |
| 5 | Evidence or stage/release gate |
| 6 | Policy or Human Gate |
| 7 | Version, migration, or adapter |
| 8 | Filesystem, lock, or transaction |
| 9 | Event integrity or replay |

## Development verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run python -m human_to_agent.services.schema_catalog --check schemas/v1
uv run pytest -q
```
