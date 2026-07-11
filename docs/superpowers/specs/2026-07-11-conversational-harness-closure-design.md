# Conversational Harness closure design

**Goal:** Let a user work only through natural conversation and supplied facts or files while the coding Agent performs every Human-to-Agent workspace operation, preserves Unknowns, and cannot promote or release unsupported claims.

## Boundary

This design does not add a chat UI or embed an LLM runtime. Codex, OpenCode, or another repository-aware coding Agent remains the conversational executor. Repository instructions define its behavior; Python services make the resulting workspace operations safe, durable, and evidence-gated.

“No threshold” means no command knowledge, templates, or prompt engineering is required from the user. It does not remove the need for real material, owner decisions, or independent evidence. Missing facts always become Unknowns.

## Guided interaction continuity

The onboarding states are routing states, not a mandatory linear questionnaire. A greeting receives a short orientation and at most one question. A message that already contains a concrete outcome skips the generic goal question. When sufficient information exists, the Agent acts without manufacturing another question.

Before a child workspace exists, discoveries are provisional conversation context. As soon as a concrete goal and real material exist, the Agent must:

1. derive and announce a safe collision-free slug;
2. run the canonical `hta workspace new` operation;
3. capture supplied text or files durably;
4. materialize confirmed constraints and every unresolved item as normative assets;
5. validate, inspect the diff, and record the change.

Explicit maintenance, review, release, migration, and resume requests bypass initial discovery and operate on the selected existing workspace.

## Safe canonical scaffold

Workspace slugs must match `^[a-z0-9]+(?:-[a-z0-9]+)*$` and be no longer than 64 characters. Validation occurs before any filesystem write.

`workspace new` renders the child template manifest instead of creating an unrelated directory-only layout. The initial scaffold contains valid draft assets rather than fake completed facts:

- `workspace.yaml` with the supplied purpose and owner;
- `README.md`, `CHANGELOG.md`, and Task Contract narrative;
- a valid draft `TASK-CONTRACT/contract.yaml` whose pending fields are explicitly non-evidence;
- an empty, valid `ASSESSMENTS/stage-state.yaml`;
- all normative directories, including `HARNESS`, `TOOLS`, `EVALUATORS`, and `ASSESSMENTS`.

The scaffold validates immediately but satisfies no promotion gate.

## Durable material capture

`capture record` accepts exactly one existing file or supplied text. It copies the exact bytes into `EVIDENCE/sources/` under a content-addressed filename and writes the Evidence asset in the same WAL transaction and event. The Evidence source locator points to the normative copy, not an absolute or temporary external path.

Deleting or moving the original input cannot break reproduction. Captured sources are included in the artifact index and release distribution. Secret-storage prohibitions remain in repository guidance; no automatic secret is treated as valid evidence.

## Normative assessment state

Add `ASSESSMENTS/stage-state.yaml` as a validated `AssessmentSnapshot`. It is the explicit fact-to-evidence map used by the existing domain gate engine. Every referenced evidence or asset ID must exist in the same normative snapshot and must not be a draft.

Mechanical facts are recomputed from assets rather than trusted from prose:

- current stage from `workspace.yaml`;
- evaluated case kinds and evaluation references from validated Cases and Evaluations;
- validated Skill count from Skill assets;
- Readiness result and reference from a validated Readiness assessment;
- initial, classified, and managed Unknown facts from actual Unknown state.

An unmanaged Unknown removes the managed-Unknown facts even if the assessment file claims them. A claimed Readiness result may be more conservative than the result recomputed from dimensions, but never more mature.

## Computed stage gates

`hta stage assess` loads the normative assessment, derives mechanical facts, and invokes `domain.stages.assess_stage` or `assess_complete_release`. It reports every gap and indeterminate fact.

`hta stage advance` repeats the computation, rejects unrecorded source changes, and advances only when the report passes. It atomically updates `workspace.yaml`, `ASSESSMENTS/stage-state.yaml`, the artifact index, and the event chain. Handwritten `.foundry/stage-*-gate.yaml` files have no authority.

Reopening a stage verifies the contradiction evidence ID exists and atomically updates both stage records.

## Computed release and complete Harness package

Release planning ignores handwritten `.foundry/release-gate.yaml`. It requires:

- current stage 5;
- a passing `assess_complete_release` report computed from the recorded normative tree;
- at least conditional Readiness that is not more mature than its dimension evidence permits;
- no unmanaged Unknown;
- a byte-matching artifact index.

Release output includes `workspace.yaml`, `ASSESSMENTS`, `HARNESS`, `TOOLS`, and `EVALUATORS` in addition to the existing public assets. The release remains deterministic and never executes an external action.

## Verification

Automated tests must prove:

1. unsafe slugs write no bytes outside `workspaces/`;
2. a new scaffold validates and cannot advance;
3. captured text and files remain reproducible after the original disappears;
4. fake handwritten stage or release gates cannot promote an empty workspace;
5. missing or draft assessment evidence is rejected;
6. unmanaged Unknowns block promotion and release;
7. the reference Pilot passes computed gates and its release contains Harness, Tool, Evaluator, assessment, and workspace assets;
8. transactions, event chains, deterministic output, adapters, schemas, lint, typing, and the complete test suite remain green.

The user will perform the final real Codex/OpenCode conversation acceptance test.
