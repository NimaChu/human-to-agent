---
name: unknown-evidence
description: Discover, classify, probe, close, and reopen Unknowns while preserving evidence and propagation history.
---

# Outcome

Discover, classify, probe, close, and reopen Unknowns while preserving evidence and propagation history.

# Inputs

A workspace ID, relevant normative source files, direct evidence references, actor identity, and the requested bounded outcome.

# Preconditions

The mother workspace is initialized; the real case or prior assessment is identifiable; required permissions are available.

# Applies when

Trigger this method when its named outcome is requested or its corresponding maturity evidence is missing.

# Does not apply when

Do not use it to invent facts, bypass a Human Gate, execute external actions, or edit generated distributions as source.

# Dependencies

The shared method contract, current Schemas, the `hf` CLI, and an independent evaluator where acceptance is claimed.

# Source-of-truth files

Read and write only the relevant files under `workspaces/<id>/`; generated `dist/` content is comparison-only.

# Procedure

Run the eleven method cards: four-quadrant inventory; blindspot pass; vocabulary teaching; contrasting design directions; intervention brainstorming; blast-radius interview; reference semantics map; tweakable plan; implementation deviation log; buy-in artifact; understanding quiz. For each Unknown, record impact, owner, evidence basis, cheapest probe, restriction, and propagation targets.

# Unknown handling

Record missing or conflicting facts as Unknowns with an owner, impact, evidence basis, cheapest probe, restriction, and propagation target.

# Human gates and stop conditions

Stop before external, irreversible, forbidden, unowned, or unsupported action. Prepare an action package when allowed; Human Gate approval never executes it.

# Evaluator and acceptance

Use explicit acceptance criteria and evidence. The implementer cannot be the sole verifier of a release or independent-reproduction claim.

# Error semantics

Report schema, reference, evidence, policy, gate, filesystem, transaction, or event failures using the stable `hf` category and exit code.

# Evidence written

Write source-linked evidence, case/evaluation or review records, Unknown history, and any implementation deviation needed to explain the result.

# Verification commands

Run `uv run hf validate --workspace <id> --format json`, then `uv run hf diff --workspace <id> --format json`; record changes only after both are understood.

