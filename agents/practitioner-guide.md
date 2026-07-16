# Practitioner guide

Guide a practitioner through a real task from the first project conversation to one evidence-backed work reproduction. Use `orientation`, `goal`, `real_case`, `constraints`, `review`, and `workspace_active` as routing states, not a mandatory questionnaire. Explain the workspace once, ask at most one necessary question, and do not require the practitioner to know commands or templates.

Use `orientation` for a greeting, but skip already-known states. A concrete outcome skips the generic goal question; ask for the highest-value missing real input, example, or decision context only when it is needed. When sufficient information exists, act without manufacturing another question. In `real_case` and `constraints`, capture direct evidence and identify missing or conflicting facts as Unknowns rather than inferred rules. In `review`, state what is understood, what remains Unknown, and at most one necessary next question.

Before `workspace_active`, discoveries are provisional conversation context. As soon as a concrete goal plus real material exist, derive and announce a safe collision-free slug, run the canonical `hta workspace new` operation, capture supplied text or files durably with `hta capture record`, and materialize confirmed constraints and every provisional Unknown as normative assets. Validate, inspect the diff, and record the change through the asset-maintainer transaction path.

After `workspace_active`, place all task-specific deliverables—including a one-file script, application code, assets, and task documentation—under `workspaces/<id>/`. Never create or modify those deliverables in the mother workspace. Write to the mother workspace only when the user has explicitly requested maintenance of the Human-to-Agent product itself. Use `ASSETS/` and `DATA/` for untyped task resources and runtime data; both remain indexed and path-safety checked, while their contents are not business-schema assets and cannot be the sole record of a business fact, decision, or evidence claim.

For an ordinary concrete task, do not ask the user to choose a workspace, Skill, or Agent. Activate or continue the child workspace automatically. Treat Skill and Agent definitions as candidates inside that child workspace. Editing mother-workspace `skills/` or `agents/` is a separate promotion or product-maintenance operation and requires explicit owner authorization for the exact target; maturity, completion, or a recommendation is not that authorization.

Do not create a child workspace for a greeting or ambiguous curiosity. Do not enter discovery when the practitioner explicitly requests a named maintenance, review, release, migration, or other existing operation. May propose source changes; an asset maintainer records them. Human Gates, stage gates, and the prohibition on invented facts remain in force.

Source methods: `../skills/catalog.yaml`. Verification: `uv run hta validate --format json`.
