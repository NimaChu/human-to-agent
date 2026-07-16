---
name: harness-composition
description: Compose validated Skills inside a child workspace; keep Harness candidates out of the mother workspace without explicit owner authorization.
---

# Outcome

Compose validated Skills into an E/T/C/S/L/V Harness with policies, state, gates, and recovery.

# Inputs

A workspace ID, relevant normative source files, direct evidence references, actor identity, and the requested bounded outcome.

# Preconditions

The mother workspace is initialized; the real case or prior assessment is identifiable; required permissions are available.

# Applies when

Trigger this method when its named outcome is requested or its corresponding maturity evidence is missing.

# Does not apply when

Do not use it to invent facts, bypass a Human Gate, execute external actions, or edit generated distributions as source.

# Dependencies

The shared method contract, current Schemas, the `hta` CLI, and an independent evaluator where acceptance is claimed.

# Source-of-truth files

Read and write only the relevant files under `workspaces/<id>/`; generated `dist/` content is comparison-only.

# Procedure

Inside the child workspace, compose Goal, Skills, Context, State, Policies, Human Gates, Exceptions, local Evaluators, final Evaluator, stop conditions, recovery, observability, and checkable completion criteria. The resulting Harness and Agent definitions remain candidates in that child workspace.

# Unknown handling

Record missing or conflicting facts as Unknowns with an owner, impact, evidence basis, cheapest probe, restriction, and propagation target.

# Human gates and stop conditions

Stop before external, irreversible, forbidden, unowned, or unsupported action. Promoting a candidate into mother-workspace `skills/` or `agents/` is a separate product-maintenance operation and requires explicit owner authorization for the exact target. Harness completion, readiness, or a recommendation is not authorization. Prepare an action package when allowed; Human Gate approval never executes it.

# Evaluator and acceptance

Acceptance requires the composed candidate to have explicit policies, state, Human Gates, stop conditions, recovery, observability, local and final evaluators, evidence links, and checkable completion criteria inside the child workspace. Acceptance does not authorize promotion into the mother workspace. The implementer cannot be the sole verifier of a release or independent-reproduction claim.

# Error semantics

Report schema, reference, evidence, policy, gate, filesystem, transaction, or event failures using the stable `hta` category and exit code.

# Evidence written

Write source-linked evidence, case/evaluation or review records, Unknown history, and any implementation deviation needed to explain the result.

# Verification commands

Run `uv run hta validate --workspace <id> --format json`, then `uv run hta diff --workspace <id> --format json`; record changes only after both are understood.
