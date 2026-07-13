# Know Your Unknowns: method cards

This public summary records the method cards distilled into Human to Agent. The
original offline HTML bundle is kept as local-only source material and is not
required by the public repository.

## Discovery

1. **Four-quadrant inventory** — separate known facts, known Unknowns, unknown
   Unknowns, and assumptions.
2. **Blindspot pass** — scan unfamiliar territory for missing questions and
   likely failure modes before implementation.
3. **Vocabulary teaching** — establish the domain terms needed to describe the
   task precisely.

## During the work

4. **Contrasting design directions** — make competing interpretations visible
   before choosing one.
5. **Intervention brainstorming** — explore bounded ways to resolve or probe an
   Unknown.
6. **Blast-radius interview** — identify who, what, and which downstream
   decisions a missing fact can affect.
7. **Reference semantics map** — use a real reference to clarify meaning when
   words alone are insufficient.
8. **Tweakable plan** — make the proposed implementation adjustable before it
   becomes expensive to change.

## After implementation

9. **Implementation deviation log** — record where the result differs from the
   intended plan and why.
10. **Buy-in artifact** — package the result, evidence, and tradeoffs for the
    people who must review it.
11. **Understanding quiz** — verify that the result and its constraints are
    understood before release or handoff.

Every Unknown remains tied to an owner, impact, evidence basis, cheapest probe,
automation restriction, and propagation target. This summary is a public
method reference; the authoritative task-specific record lives under
`workspaces/<id>/`.
