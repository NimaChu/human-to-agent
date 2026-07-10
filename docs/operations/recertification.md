# Re-certification

The version vector covers CLI, Schema, templates, Skill catalog, Harness, tool contracts, model assumptions, and environment assumptions. Compare vectors whenever any component changes.

Skill-contract and golden-case changes rerun Skill cases and dependent contracts. Harness-core changes require `stage4_e2e` and `stage5_readiness`. Permission or side-effect changes rerun policy, Human Gate, idempotency, and retry evidence. Major Schema and invalidated-assumption changes require full validation and Readiness.

Blocking changes prevent release until every required evaluation has direct evidence. Adapter source-digest drift is a version error and requires re-certification. Record the change, reverse dependents, reasons, required evaluations, owner, and outcome before rebuilding.
