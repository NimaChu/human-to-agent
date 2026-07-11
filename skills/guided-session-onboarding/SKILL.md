---
name: guided-session-onboarding
description: Start every new project conversation with one-question evidence-first guidance and safely enter a real child workspace.
---

# Outcome

Guide a new project conversation from a natural-language opening to an evidence-backed child workspace without requiring the user to know commands, templates, or directory layout.

# Inputs

The user's first message, any supplied material, current project guidance, existing child-workspace identifiers, and the requested outcome or explicit operation.

# Preconditions

The repository guidance and shared methods are available. A user may begin with a greeting, a broad intention, or a concrete real task.

# Applies when

Apply this method at the start of every new project conversation unless the user explicitly requests a named maintenance, review, release, migration, or other existing operation.

# Does not apply when

Do not use this method to create a child workspace for an ambiguous greeting, invent facts, bypass stage gates or Human Gates, execute external actions, or treat generated `dist/` files as source.

# Dependencies

The shared method contract, practitioner-guide role, `hta` CLI, workspace schemas, Unknown lifecycle, Human Gates, and asset-maintainer transaction path.

# Source-of-truth files

Read repository guidance and shared methods first. After activation, read and write only normative source files under `workspaces/<id>/`; generated `dist/` content is comparison-only.

# Procedure

Use these states in order, returning to an earlier state when evidence changes:

1. `orientation`: explain Human-to-Agent once and ask one necessary question: what result does the user want to achieve?
2. `goal`: restate the credible outcome and ask for the highest-value real input, example, or decision context.
3. `real_case`: inspect the supplied material and ask one necessary question for the highest-impact missing fact, boundary, or expected result.
4. `constraints`: capture confirmed boundaries, direct evidence, and restrictions; record missing or conflicting facts as Unknowns.
5. `review`: state what is understood, what remains Unknown, and the one next question.
6. `workspace_active`: after a concrete goal plus a real input, example, or decision context exist, derive a collision-free slug, state it, create or select the child workspace, and continue through the existing five-stage method.

Do not require the user to run commands. Use permitted workspace mechanics on their behalf and ask only one necessary question in each response.

# Unknown handling

Every missing, conflicting, or unverified fact becomes an explicit Unknown with evidence basis, owner, impact, cheapest probe, restriction, and propagation target. Never convert conversational confidence into a proven rule.

# Human gates and stop conditions

Stop before external, irreversible, forbidden, unowned, or unsupported action. Do not advance a stage, close an Unknown, or prepare a release without the existing direct evidence and Human Gate requirements.

# Evaluator and acceptance

The onboarding result is acceptable when the Agent has introduced the workspace once, asked one necessary question, avoided user CLI burden, and created no workspace before a concrete goal plus real context exist. Existing evaluators independently assess later cases, stages, readiness, and releases.

# Error semantics

Report missing context as an Unknown or a single next question. Report schema, reference, evidence, policy, gate, filesystem, transaction, or event failures using the stable `hta` category and exit code.

# Evidence written

Write direct source-linked evidence, real-case captures, Task Contract fields, Unknown history, case and evaluation records, and implementation deviations only after the existing workspace lifecycle has activated.

# Verification commands

Run `uv run hta validate --workspace <id> --format json`, then `uv run hta diff --workspace <id> --format json`; record changes only after both are understood through `uv run hta record-change --workspace <id> --format json`.
