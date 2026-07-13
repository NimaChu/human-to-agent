# Human to Agent agent guidance

## New project conversations

- In every new project conversation, briefly explain that Human-to-Agent turns a real task into an evidence-backed child workspace and that the user does not need to know commands or templates. Ask at most one necessary question.
- Treat onboarding states as routing states and skip already-known states. If the user has not stated a credible task goal, ask what result they want. If they already supplied a concrete outcome, skip the generic goal question and ask only for the highest-value missing real input, example, or decision context. When sufficient information exists, act without manufacturing another question.
- Do not require the user to run `hta` commands or complete a form; manage permitted workspace mechanics on their behalf.
- Do not create a child workspace for a greeting or ambiguous curiosity. Before activation, keep discoveries as provisional conversation context. As soon as a concrete goal plus real material exist, derive and announce a safe collision-free slug, run the canonical `hta workspace new` operation, capture supplied text or files durably with `hta capture record`, and materialize confirmed constraints and every provisional Unknown as normative assets. Then validate, inspect the diff, and record the change.
- Do not enter this discovery protocol when the user explicitly requests a named maintenance, review, release, migration, or other existing operation.
- After activation, all task-specific deliverables—including a one-file script, application code,
  assets, or task documentation—belong under `workspaces/<id>/`. Never create or modify those
  deliverables in the mother workspace. Write to the mother workspace only when the user has
  explicitly requested maintenance of the Human-to-Agent product itself.

- Treat `workspaces/` Markdown, YAML, and JSONL as the only business source of truth.
- Use each child workspace's `ASSETS/` and `DATA/` directories for untyped task resources and
  runtime data. They are indexed and path-safety checked but not business-schema assets; do not
  make them the only record of a business fact, decision, or evidence claim.
- Never use `dist/` as business input or edit generated files as authoritative data.
- Run changes through `uv`; use `uv run pytest`, `uv run ruff check`, and `uv run mypy`.
- Follow red-green-refactor TDD for every behavior change.
- Preserve evidence basis, Unknown history, Human Gates, and append-only events.
- Never invent a business rule to make a stage gate pass.
- Never infer autonomy approval from Readiness, a requested autonomy level, or conversational confidence. Only record `LOOP-READINESS/autonomy-approval.yaml` after capturing direct owner evidence for the exact level and workspace; otherwise keep approval missing or Unknown.
- Never store credentials or secrets in the workspace or its event logs.
- Keep Codex and OpenCode adapters thin; shared methods live in `skills/` and `agents/`.
- External and irreversible actions may only produce an unexecuted action package; obey every Human Gate and recovery entry.
- Before recording source changes, run `uv run hta validate --workspace <id> --format json` and `uv run hta diff --workspace <id> --format json`.
- Before claiming completion, run `uv run ruff check .`, `uv run mypy src tests`, and `uv run pytest -q` plus the relevant release or event verification command.
