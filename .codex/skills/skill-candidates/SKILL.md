---
name: skill-candidates
description: Identify reusable Skill candidates inside a child workspace; never promote them into the mother workspace without explicit owner authorization.
---

Source: `../../../skills/skill-candidates/SKILL.md`

Permission: obey the source method, repository AGENTS.md, and Human Gates.
Discovery: use this adapter only to locate the shared method; it contains no business rules.
Invocation: run `uv run hta validate --workspace <id> --format json` before recording any source change.
