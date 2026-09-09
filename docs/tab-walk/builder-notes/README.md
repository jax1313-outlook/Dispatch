# Builder Notes

Ideas and questions that have to be dealt with before a build list can be
finalized. Not findings, not decisions, not a backlog.

A finding says what a screen does. A builder note says what we do not yet know
well enough to build against. The distinction matters because a build list
written on top of an assumption produces work that has to be redone.

## When something belongs here

- A question raised by looking at a screen that the screen cannot answer
- An assumption the walk has been carrying without evidence
- A concept that needs defining before code can be written against it
- Anything where the honest answer is "we have not established that"

## When it does not

- A defect in a screen. That is a finding, in the tab's `FINDINGS.md`.
- Something removed and set aside. That is `../PARKING_LOT.md`.
- A settled question. That is `../LENS.md` or `DECISION_LOG.md` at the repo root.

## Rules

One file per note. Name it for the question, not the answer.

Every claim carries its evidence class. The walk does not infer runtime
behavior from code structure alone, so a note must say which of these applies:

| Class | Means |
| --- | --- |
| Proven by repository evidence | An artifact, a record or a run exists and was inspected |
| Implemented but unverified | The code path exists and was read, but nothing shows it has run |
| Assumed by doctrine | A document says it should be so; nothing shows that it is |
| Missing | Nothing implements it |

A note stays open until Mike answers it. Record the answer in the note, dated,
and then say what it changed.

## Notes

- [Are alerts detected, generated, delivered, and tracked?](alerts-detection-generation-delivery-tracking.md) — opened 2026-09-09, decided 2026-09-09. Design settled, build parked.
- [Where does the opportunity card belong?](opportunity-card-placement.md) — opened 2026-09-09, open. Placement and ownership, not redesign. Deferred until Load Search and SAM are walked.
- [The Owner/Operator Scoreboard](owner-operator-scoreboard.md) — opened 2026-09-09, open. Freight decision support, not accounting. Almost none of it is built.
