# Harness Foundry

Harness Foundry is a file-first mother workspace for evolving a real task through
work reproduction, task contracts, validated Skills, controlled Harnesses, and
Loop Readiness certification.

Business facts live in Markdown, YAML, and JSONL. The `hf` CLI validates and
generates deterministic child workspaces; it is not a second source of truth.

## Development

```powershell
python -m pip install uv
uv sync --all-groups
uv run hf version --format json
uv run pytest -q
```

See `docs/superpowers/specs/2026-07-10-harness-foundry-design.md` and
`docs/superpowers/plans/2026-07-10-harness-foundry-implementation.md` for the
approved design and implementation plan.

