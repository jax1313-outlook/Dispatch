# Tab Walk — Dispatch

- Status: NOT STARTED
- Walked on:
- Finding ID prefix: DISPATCH

## Scope

Nav entries: Dispatch, Operations, Calendar, Exceptions

Templates: dispatch.html, dispatch_detail.html, dispatch_decision.html, operations.html, calendar.html, exceptions.html, _sweep_panel.html

Routes:

## What this tab is supposed to do

One paragraph, in Joe's words, not the code's. If this cannot be written
without reading the source first, that gap is itself a finding.

## What it actually does

What happened when the page was opened against real data. Name the load or
record used, so the walk can be repeated later and get the same result.

## The six questions

Read against `docs/architecture/DISPATCH_WORKER_CONSTITUTION_ARCHITECTURE.md`.
See `docs/tab-walk/LENS.md` for how to apply these and what already conflicts.
A question that cannot be answered is a finding. Record it as one.

**1. Which worker owns this function?**

**2. Is the tab displaying workflow, or defining workflow?**

**3. Is worker responsibility incorrectly embedded in the screen?**

**4. What state transition does this screen represent?**

**5. What inputs, outputs, and handoffs are present?**

- Receives:
- Produces:
- Hands off to:
- Handoff condition:

**6. Does the current implementation align with worker ownership?**

## Findings

Every finding gets an ID. Never renumber. A closed finding keeps its number
so commits and tests can keep pointing at it.

### DISPATCH-001 — short title

- Severity: blocker | broken | wrong | rough | cosmetic
- Status: open | fixed | wont-fix | deferred
- Lens: yes | no — yes if worker ownership, handoffs, states and screens are
  mixed together here. Lens findings are understanding, not a work order.
- Evidence: evidence/filename
- Seen: what was observed, exactly, including any error text
- Expected: what should have happened instead
- Cause: fill in only when actually traced. Leave blank rather than guessing.
- Fix: the commit or branch that closed it
- Proven: date this was confirmed working on Mike's laptop with a real load

## Decisions made during this walk

Decisions that change behavior belong in DECISION_LOG.md at the repo root.
Record the decision ID here and do not restate the decision itself.

## Carried forward

Anything this tab depends on that a different tab owns. Name that tab.
