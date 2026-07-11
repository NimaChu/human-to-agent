# Human to Agent agent guidance

## New project conversations

- In every new project conversation, begin with a concise explanation that Human-to-Agent turns a real task into an evidence-backed child workspace and that the user does not need to know commands or templates.
- If the user has not stated a credible task goal, end the first response by asking what result they want to achieve. If they have stated a goal, acknowledge it and ask only the highest-value missing real input, example, or decision context.
- Ask one necessary question at a time. Do not require the user to run `hta` commands or complete a form; manage permitted workspace mechanics on their behalf.
- Do not create a child workspace for a greeting or ambiguous curiosity. Create it only after a concrete goal plus a real input, example, or decision context; state the derived slug before creating it.
- Do not enter this discovery protocol when the user explicitly requests a named maintenance, review, release, migration, or other existing operation.

- Treat `workspaces/` Markdown, YAML, and JSONL as the only business source of truth.
- Never use `dist/` as business input or edit generated files as authoritative data.
- Run changes through `uv`; use `uv run pytest`, `uv run ruff check`, and `uv run mypy`.
- Follow red-green-refactor TDD for every behavior change.
- Preserve evidence basis, Unknown history, Human Gates, and append-only events.
- Never invent a business rule to make a stage gate pass.
- Never store credentials or secrets in normative sources or event logs.
- Keep Codex and OpenCode adapters thin; shared methods live in `skills/` and `agents/`.
- External and irreversible actions may only produce an unexecuted action package; obey every Human Gate and recovery entry.
- Before recording source changes, run `uv run hta validate --workspace <id> --format json` and `uv run hta diff --workspace <id> --format json`.
- Before claiming completion, run `uv run ruff check .`, `uv run mypy src tests`, and `uv run pytest -q` plus the relevant release or event verification command.
