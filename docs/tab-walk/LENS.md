# The Lens

Every tab in this walk is read through the worker constitution architecture, at
`docs/architecture/DISPATCH_WORKER_CONSTITUTION_ARCHITECTURE.md`.

The objective is understanding before redesign. Working capability is preserved. No broad
refactor is initiated from this walk. Findings are identified, not acted on. Mike retains
final authority.

## The six questions

Every tab answers all six, in its `FINDINGS.md`. A question that cannot be answered is
itself a finding, and should be recorded as one rather than left blank.

1. **Which worker owns this function?**
2. **Is the tab displaying workflow, or defining workflow?**
3. **Is worker responsibility incorrectly embedded in the screen?**
4. **What state transition does this screen represent?**
5. **What inputs, outputs, and handoffs are present?**
6. **Does the current implementation align with worker ownership?**

Question 2 is the one that catches the most. A screen that decides something is a screen
holding a worker's responsibility. Per the constitution, screens are presentation layers
and do not define workflow.

## What counts as a lens finding

Flag it when worker ownership, handoffs, states, and screens are mixed together in one
place. Specifically:

- A screen that performs work a worker should own
- A handoff that happens implicitly, because a screen was opened, rather than because a
  defined condition was met
- A state transition with no single owner, or with more than one
- A worker reaching past its boundary, especially anything that commits rather than
  recommends or produces
- Work that arrives somewhere with no defined sender, or leaves with no defined receiver

Record these under the normal finding format with severity and status like any other. Add
the line `Lens: yes` so they can be pulled out as a set at the end of the walk.

## Open questions, unresolved

These surfaced when the constitution was read against what is already in the repository.
None of them are resolved here. They are listed so the walk does not silently pick a side,
and so the same question is not re-argued on twelve separate tabs.

**Workers or departments.** The repository already calls Intelligence, Library, Publisher
and Archive a tri-department set with shared object contracts. The constitution calls them
workers and adds Joe and Dispatch. Same nouns, two vocabularies. Until Mike settles it,
findings should use the constitution's word and name the doctrine file they are reading
against.

**Manager already holds the handoff seat.** `docs/MANAGER.md` documents Manager as
dormant, never built, sitting over Intelligence, Library, Publisher and Archive, receiving
their output, presenting it for review, and routing decisions. That is close to the
function the constitution identifies as the missing artifact. The walk must not build
Manager as a side effect of documenting handoffs. Manager's status is Mike's to change.

**One record or three objects.** `docs/DISPATCH_STATE_TRANSITION_RULES.md` opens with one
record, one identity, and holds that purpose changes while identity does not. The
constitution's transition reads as object replacement: Opportunity Card becomes Committed
Load becomes Load Card or Mission Record. These may be the same thing said two ways, or
they may conflict. Question 4 on every tab depends on which it is, so resolve it early.

**Three meanings of JOE.** The repository's doctrine files describe JOE as a dialog
assistant and narration layer, explicitly optional, with records displaying without
narrative when it is unavailable. The constitution lists Joe as a worker that owns work.
On the joe-portal branch, JOE Portal is the booking workbench holding Candidates, Booking
and New Mission. Three different things share one name.

**Level 2 partly exists.** The constitution's Level 2 chain runs from opportunity
discovery to archive. `docs/DISPATCH_STATE_TRANSITION_RULES.md` already covers activation
events, atomic human gates, run phases, and transitions that must never happen. Level 2
should be reconciled with that file, not written fresh alongside it.
