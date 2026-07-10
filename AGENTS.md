# Harness Foundry agent guidance

- Treat `workspaces/` Markdown, YAML, and JSONL as the only business source of truth.
- Never use `dist/` as business input or edit generated files as authoritative data.
- Run changes through `uv`; use `uv run pytest`, `uv run ruff check`, and `uv run mypy`.
- Follow red-green-refactor TDD for every behavior change.
- Preserve evidence basis, Unknown history, Human Gates, and append-only events.
- Never invent a business rule to make a stage gate pass.
- Never store credentials or secrets in normative sources or event logs.
- Keep Codex and OpenCode adapters thin; shared methods live in `skills/` and `agents/`.
- External and irreversible actions may only produce an unexecuted action package; obey every Human Gate and recovery entry.
- Before recording source changes, run `uv run hf validate --workspace <id> --format json` and `uv run hf diff --workspace <id> --format json`.
- Before claiming completion, run `uv run ruff check .`, `uv run mypy src tests`, and `uv run pytest -q` plus the relevant release or event verification command.
