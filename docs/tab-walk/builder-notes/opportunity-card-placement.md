# Where does the opportunity card belong?

- Opened: 2026-09-09, by Mike, during the tab 01 walk
- Status: OPEN — decision deferred until Load Search and SAM are walked
- This is a placement and ownership review, not a redesign request

## Mike's discovery

The opportunity cards on the Dispatch screen are one of the strongest
operational presentation components in the system. Low cognitive load, easy to
scan, easy to compare, decision focused, operationally useful. A mature
evolution of the original SAM opportunity cards.

The cards are not the problem. The location is likely wrong.

**Do not redesign the cards. Do not replace the cards.** The existing
presentation is preserved.

## Operational context

When driving: Driver Portal. When parked safely with a tablet or laptop
connected to the node: Operations Portal.

At that point the purpose is not mission execution. It is reviewing
opportunities, evaluating Intelligence findings, comparing loads, considering
capacity, and making commitment decisions. These cards support that activity
extremely well.

## Worker model

```
Intelligence Worker
  collect, analyze, score, sort, recommend
        ↓
  produces Opportunity Cards
        ↓
  Operations Portal
        ↓
  Mike reviews
        ↓
  commit / reject / continue review
```

## Lifecycle

```
Raw Opportunity → Intelligence Analysis → Opportunity Card →
Operations Review → Mike Decision → Committed Load →
Mission Record → Active Load → Archive
```

The card remains largely the same throughout. Graphics, actions and status
indicators evolve as state changes. This is consistent with R1: one record, one
identity, the name and purpose changing at the gates.

## Key observation

The card appears correct. The screen ownership appears wrong. This feels more
like Operations Portal leading to Opportunity Review than like Dispatch
Workflow.

## Open question

Should these cards become the primary review surface of the Operations Portal?

Possible future layout: Operations Portal, then Opportunity Review, then
Opportunity Cards. Candidate homes named so far are Load Search, Load Sweeper,
and Opportunity Review.

Deferred until Load Search is walked, SAM is walked, and further tab-walk
findings are in.

## What the repository shows

Four facts that bear on the placement question. All proven by inspection of the
`main` branch on 2026-09-09.

**1. The card was not a component. RESOLVED 2026-09-09.**

Corrected on closer reading. It was hand-copied four times across two families,
not five times across one.

| Family | Full density | Compact density |
| --- | --- | --- |
| Freight opportunity card | `dispatch.html` | Home top-loads strip |
| SAM contract opportunity card | `sam.html` | Home top-opportunities strip |

`pending.html` renders a different card entirely, priority-driven with no
Intelligence score. `brief.html` is the detail view, not a card. Neither was in
scope.

There was not a single `{% include %}` anywhere in the template set, so every
instance was hand-copied and the copies had already drifted. The compact freight
card carried a SAMPLE DATA badge that the full one did not.

Mike directed the extraction on 2026-09-09. There are now two macro partials,
`_card_dispatch.html` and `_card_sam.html`, each with a compact and a full
density. 179 lines of duplicated markup collapsed into two files.

Presentation did not change. Proven by rendering Home, Dispatch and SAM against
the same fixture data before and after, and diffing: identical output apart from
indentation.

Placement is now a single decision rather than four.

**2. Load Search has no card surface today.**

`search.html` renders five data tables: Loads, Drivers, Equipment, Settlements
and Broker Contacts. No cards at all. So "these should be what Load Search is"
is not a relocation. The card would have to arrive on a screen that has never
had one, and the table view would have to be replaced or moved.

**3. The Load Sweeper is not in the running build.**

`dispatch/sweep.py` and `_sweep_panel.html` exist only on the unmerged
`merge/main-into-joe-portal` branch. Neither is on `main`, which is what Mike is
running. Naming the sweeper as a home for the card means deciding what happens
to that branch first.

**4. Ownership is already settled even though placement is not.**

Under the constitution, Intelligence owns the entire pre-commit lifecycle and
produces the Opportunity Card. Under R3, the booking workbench sits in the
Pre-Commitment Lifecycle. So Intelligence owns this card no matter which screen
displays it. Mike's worker model above says the same thing.

That means question 1 of the six has an answer here, and only question 2 is
open: the tab is displaying an Intelligence product, and the question is which
tab should do the displaying.

## Related

Tab 02 is Pre-Commitment Lifecycle and covers Load Search and SAM. This note
should be read before that tab is walked, and answered after.

## Answer

Not yet answered.
