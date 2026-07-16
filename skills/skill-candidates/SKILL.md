---
name: skill-candidates
description: Identify reusable Skill candidates inside a child workspace; never promote them into the mother workspace without explicit owner authorization.
---

# Outcome

Identify reusable Skill candidates from repeated evidence-backed task steps and explicit boundaries.

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

Inside the child workspace, cluster repeatable steps, separate business judgment, define triggers and non-triggers, specify inputs and outputs, link normal/boundary/failure cases and evaluators, define checkable completion criteria, and leave uncertain candidates as Unknowns. Candidate discovery does not edit mother-workspace `skills/` or `agents/`.

# Unknown handling

Record missing or conflicting facts as Unknowns with an owner, impact, evidence basis, cheapest probe, restriction, and propagation target.

# Human gates and stop conditions

Stop before external, irreversible, forbidden, unowned, or unsupported action. Promoting a candidate into mother-workspace `skills/` or `agents/` is a separate product-maintenance operation and requires explicit owner authorization for the exact target. A mature candidate, passed evaluator, or recommendation is not authorization. Prepare an action package when allowed; Human Gate approval never executes it.

# Evaluator and acceptance

A candidate is acceptable only when its triggers, non-triggers, inputs, outputs, dependencies, Human Gates, evaluator, evidence cases, and checkable completion criteria are explicit inside the child workspace. This acceptance does not authorize promotion into the mother workspace. The implementer cannot be the sole verifier of a release or independent-reproduction claim.

# Error semantics

Report schema, reference, evidence, policy, gate, filesystem, transaction, or event failures using the stable `hta` category and exit code.

# Evidence written

Write source-linked evidence, case/evaluation or review records, Unknown history, and any implementation deviation needed to explain the result.

# Verification commands

Run `uv run hta validate --workspace <id> --format json`, then `uv run hta diff --workspace <id> --format json`; record changes only after both are understood.
