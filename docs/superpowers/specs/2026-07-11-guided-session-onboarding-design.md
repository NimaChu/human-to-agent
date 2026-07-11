# Guided session onboarding design

**Goal:** Make every new conversation opened in the Human-to-Agent repository begin in a low-friction, agent-led discovery mode. The user can speak naturally; the agent explains the workspace briefly, asks one necessary question at a time, and uses the existing child-workspace workflow once a real task is sufficiently understood.

## Scope and integration

This is an interaction-policy change, not a new runtime, CLI wizard, or parallel methodology. It extends the existing `practitioner-guide` role, shared method contract, workspace lifecycle, stage gates, Unknown model, Human Gates, adapters, and validation commands.

The policy applies to a new project conversation before a child workspace has been selected. It does not override a user who explicitly requests a maintenance, review, release, migration, or other named operation.

## First-turn behavior

For every new project conversation, the agent begins with a concise orientation that says:

1. Human-to-Agent turns a real task into an evidence-backed, reusable child workspace.
2. The user does not need to know commands, templates, or directory structure.
3. The agent will ask one necessary question at a time and manage workspace mechanics.
4. The user may describe a desired result or provide existing material.

The first turn ends with exactly one invitation: ask what result the user wants to achieve. If the user's first message already contains a credible task goal, the agent acknowledges it and asks only for the highest-value missing real input instead of repeating the generic invitation.

## Guided discovery protocol

The agent maintains a compact conversational state: `orientation`, `goal`, `real_case`, `constraints`, `review`, and `workspace_active`.

- In `orientation`, answer a casual greeting with the orientation and one goal question.
- In `goal`, restate the intended outcome in plain language and ask for one real example, source artifact, or decision the user wants the future Agent to make.
- In `real_case`, inspect the supplied material, identify the highest-impact missing fact or boundary, and ask only that question. Do not request a form or long prompt.
- In `constraints`, record confirmed constraints, direct evidence, and explicit Unknowns. A missing fact becomes an Unknown; it is never silently inferred.
- In `review`, show a short status: what is understood, what remains Unknown, and the single next question.
- In `workspace_active`, continue using the same one-question rule while the existing five-stage lifecycle, validation, evidence, and Human Gate rules govern the work.

The agent must not require the user to run `hta` commands. It may run the commands and edit normative source files on the user's behalf where the existing project policy permits.

## Child-workspace creation boundary

The agent creates a child workspace only after it has an identifiable goal and at least one real input, example, or decision context. It derives a short slug, checks for a collision, tells the user the chosen name, and creates the workspace through the existing `hta workspace new` path.

An ambiguous greeting, idle conversation, or broad curiosity must not create files. An explicit maintenance or review request may operate on an existing workspace without entering discovery mode.

## Safety and continuity

The onboarding policy preserves the established controls:

- Direct evidence remains required for stage and release gates.
- Unknowns remain visible and retain their history.
- `record-change` remains the only path for recording normative source changes.
- Human Gates retain authority over external, irreversible, or high-risk actions.
- `dist/` remains generated output and never becomes business input.
- The first release remains non-interactive at runtime; this policy governs how a coding Agent collaborates in a project conversation, not a user-facing product UI.

## Source layout and adapters

Add a shared `skills/guided-session-onboarding/SKILL.md` that defines the protocol and refers to the shared method contract. Add thin Codex and OpenCode adapters that point to the shared skill. Add the skill to `skills/catalog.yaml` and update catalog digests.

Update `AGENTS.md` to make guided onboarding the default for a new project conversation and to list the explicit-operation exception. Extend `agents/practitioner-guide.md` so it owns the discovery protocol after the first turn. Update README guidance from command-first onboarding to conversational onboarding, while retaining the CLI reference for maintainers.

## Tests

Add contract tests that assert:

1. `AGENTS.md` requires default new-session orientation, one-question progression, and no user CLI burden.
2. The shared guided-session skill defines all six states, the workspace-creation boundary, Unknown behavior, and explicit-operation exception.
3. Codex and OpenCode adapters are present, thin, and resolve to the shared skill.
4. The practitioner guide and shared method contract remain consistent with one-question, evidence-first discovery.

Existing adapter integrity and documentation tests remain authoritative and must pass unchanged except for expected catalog and adapter additions.

## Acceptance criteria

A new user can enter the project and say only “hello” or a natural-language task description. The Agent explains the purpose once, asks only one relevant question, never asks the user to learn commands, does not create a child workspace prematurely, and transitions into the existing evidence-backed workflow when enough real context exists.
