# Human to Agent

Human to Agent is a file-first mother workspace for turning a real task into an evidence-backed Task Contract, validated Skills and cases, a controlled E/T/C/S/L/V Harness, and a Loop Readiness decision. Markdown, YAML, and JSONL under `workspaces/` are authoritative; `dist/` is generated and never becomes business input.

## Bootstrap

```powershell
python -m pip install uv
uv sync --frozen --all-groups
uv run hta version --format json
uv run hta init
```

## Five-stage happy path

All commands are non-interactive. Replace `<workspace>` with the child-workspace slug.

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

Draft builds are allowed at any stage and contain a visible `DRAFT` warning. Release builds require a passing complete-release gate, at least conditional Readiness, and an artifact index matching every normative source byte. `BUILD-MANIFEST.json` contains deterministic versions, source digest, and per-file digests—never a clock or random ID.

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
