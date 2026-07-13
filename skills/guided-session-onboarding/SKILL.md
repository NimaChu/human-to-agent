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

Read repository guidance and shared methods first. After activation, read and write normative source files and task assets only under `workspaces/<id>/`; generated `dist/` content is comparison-only. Put all task-specific deliverables—including a one-file script, application code, assets, and task documentation—under `workspaces/<id>/`. Never create or modify those deliverables in the mother workspace. Write to the mother workspace only when the user has explicitly requested maintenance of the Human-to-Agent product itself. Use `ASSETS/` and `DATA/` for untyped task resources and runtime data: they are indexed and path-safety checked, but their contents are not business-schema assets and cannot be the sole record of a business fact, decision, or evidence claim.

# Procedure

Use these as routing states, not a mandatory linear questionnaire. Skip already-known states, ask at most one necessary question in a response, and act without manufacturing another question when sufficient information exists:

1. `orientation`: for a greeting or ambiguous opening, explain Human-to-Agent once and ask what result the user wants to achieve.
2. `goal`: if a credible outcome is not already known, establish it. A message that already contains a concrete outcome skips the generic goal question; ask for the highest-value missing real input, example, or decision context only when needed.
3. `real_case`: inspect the supplied material and ask one necessary question for the highest-impact missing fact, boundary, or expected result.
4. `constraints`: capture confirmed boundaries, direct evidence, and restrictions; record missing or conflicting facts as Unknowns.
5. `review`: when a review is useful, state what is understood, what remains Unknown, and at most one necessary next question.
6. `workspace_active`: as soon as a concrete goal plus real material exist, perform the canonical activation handoff below and continue through the existing five-stage method.

For the activation handoff:

1. Derive and announce a safe collision-free slug.
2. Run the canonical `hta workspace new` operation.
3. Capture every supplied text or file durably with `hta capture record`.
4. Materialize confirmed constraints and every provisional Unknown as normative assets.
5. Validate, inspect the diff, and record the change.

Do not require the user to run commands. Use permitted workspace mechanics on their behalf. Explicit maintenance, review, release, migration, resume, and other named existing-workspace operations bypass initial discovery and operate on the selected workspace.

# Unknown handling

Before a child workspace exists, discoveries are provisional conversation context. After activation, every missing, conflicting, or unverified fact becomes an explicit normative Unknown with evidence basis, owner, impact, cheapest probe, restriction, and propagation target. Never convert conversational confidence into a proven rule.

# Human gates and stop conditions

Stop before external, irreversible, forbidden, unowned, or unsupported action. Do not advance a stage, close an Unknown, or prepare a release without the existing direct evidence and Human Gate requirements.

Never infer autonomy approval from Readiness, a requested level, or conversational confidence. Capture direct owner evidence for the exact workspace and level before writing `LOOP-READINESS/autonomy-approval.yaml`; when that evidence is absent or ambiguous, keep approval missing and record the uncertainty as an Unknown.

# Evaluator and acceptance

The onboarding result is acceptable when the Agent has introduced the workspace once, asked at most one necessary question per response, skipped states already satisfied by supplied facts, avoided user CLI burden, and created no workspace before a concrete goal plus real context exist. Existing evaluators independently assess later cases, stages, readiness, and releases.

# Error semantics

Report missing context as an Unknown or a single next question. Report schema, reference, evidence, policy, gate, filesystem, transaction, or event failures using the stable `hta` category and exit code.

# Evidence written

Write direct source-linked evidence, real-case captures, Task Contract fields, Unknown history, case and evaluation records, and implementation deviations only after the existing workspace lifecycle has activated.

# Verification commands

Run `uv run hta validate --workspace <id> --format json`, then `uv run hta diff --workspace <id> --format json`; record changes only after both are understood through `uv run hta record-change --workspace <id> --format json`.
