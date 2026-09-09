# Tab Walk — Fleet

- Status: NOT STARTED
- Walked on:
- Finding ID prefix: FLEET

## Scope

Nav entries: Fleet

Templates: fleet.html, equipment_detail.html

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

### FLEET-001 — short title

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


### FLEET-001 — Fleet cannot be removed; Settings does not contain its functions

- Severity: n/a — this is a blocked removal, not a defect
- Status: open — needs Mike's ruling
- Lens: yes
- Evidence: `portal/templates/settings.html`, `portal/templates/fleet.html`,
  `portal/templates/search.html:82` and `:113`
- Seen: Mike proposed removing Fleet on 2026-09-09, conditional on nothing under
  it being needed elsewhere. The condition is not met, on two counts.

  **Settings does not manage drivers or equipment.** It has eleven sections:
  storage roots, resolved paths, portal configuration, integration status,
  acquisition, email delivery, stall thresholds, system keys, accounting and
  doctrine reference. None of them touch the roster. Fleet is the only screen
  with Add Driver and Add Equipment, the only view of the roster, and the only
  view of driver-to-equipment assignments.

  **Load Search links into Fleet.** Its driver rows link to the Fleet driver
  detail page and its equipment rows link to the Fleet equipment detail page.
  Removing those routes breaks two columns of Load Search.

- Expected: if Fleet goes, driver and equipment management has to exist
  somewhere first, and Load Search needs somewhere to point.
- Cause: the premise looks like it came from what Settings is named rather than
  what it holds. Settings is configuration. Fleet is a roster.
- Fix:
- Proven:

The service layer underneath is used well beyond the Fleet tab and is not at
issue. Dispatch reads active drivers and equipment for its assignment dropdowns,
the driver portal reads active equipment, and the dispatch API owns create,
list and assign. None of that lives in the Fleet tab; the tab is the only user
interface onto it.

Three ways forward, all Mike's call:

1. Keep Fleet as it is and revisit after the walk.
2. Move driver and equipment management into Settings first, then remove Fleet
   and repoint Load Search.
3. Remove the Fleet tab from the nav but keep the routes, so Load Search still
   works and the roster is reachable by URL. This is the reversible option and
   matches what was done with SAM.

## Decisions made during this walk

Decisions that change behavior belong in DECISION_LOG.md at the repo root.
Record the decision ID here and do not restate the decision itself.

## Carried forward

Anything this tab depends on that a different tab owns. Name that tab.
