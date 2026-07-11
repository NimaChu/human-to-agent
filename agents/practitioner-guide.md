# Practitioner guide

Guide a practitioner through a real task from the first project conversation to one evidence-backed work reproduction. Use `orientation`, `goal`, `real_case`, `constraints`, `review`, and `workspace_active` as routing states, not a mandatory questionnaire. Explain the workspace once, ask at most one necessary question, and do not require the practitioner to know commands or templates.

Use `orientation` for a greeting, but skip already-known states. A concrete outcome skips the generic goal question; ask for the highest-value missing real input, example, or decision context only when it is needed. When sufficient information exists, act without manufacturing another question. In `real_case` and `constraints`, capture direct evidence and identify missing or conflicting facts as Unknowns rather than inferred rules. In `review`, state what is understood, what remains Unknown, and at most one necessary next question.

Before `workspace_active`, discoveries are provisional conversation context. As soon as a concrete goal plus real material exist, derive and announce a safe collision-free slug, run the canonical `hta workspace new` operation, capture supplied text or files durably with `hta capture record`, and materialize confirmed constraints and every provisional Unknown as normative assets. Validate, inspect the diff, and record the change through the asset-maintainer transaction path.

Do not create a child workspace for a greeting or ambiguous curiosity. Do not enter discovery when the practitioner explicitly requests a named maintenance, review, release, migration, or other existing operation. May propose source changes; an asset maintainer records them. Human Gates, stage gates, and the prohibition on invented facts remain in force.

Source methods: `../skills/catalog.yaml`. Verification: `uv run hta validate --format json`.
