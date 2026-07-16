---
name: harness-composition
description: Compose validated Skills inside a child workspace; keep Harness candidates out of the mother workspace without explicit owner authorization.
---

Source: `../../../skills/harness-composition/SKILL.md`

Permission: obey the source method, repository AGENTS.md, and Human Gates.
Discovery: use this adapter only to locate the shared method; it contains no business rules.
Invocation: run `uv run hta validate --workspace <id> --format json` before recording any source change.
