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

## Settled by Mike, 2026-09-09

These were open when the constitution was first read against the repository. Mike closed
them. They are settled for the purpose of the walk. Findings use these answers.

**R1 — One record, not three objects.** The Opportunity Card is updated as negotiation
proceeds. When Mike presses Accept, the card changes name and carries all of its encoded
data forward through the end-to-end process. The record's identity persists the whole way.

This confirms `docs/DISPATCH_STATE_TRANSITION_RULES.md`, which already holds one record,
one identity, purpose changes while identity does not. The constitution's arrows are a
change of name and purpose, not a replacement of the object. Accept is the commit gate.

Question 4 on every tab is therefore asking which named phase of one record the screen
shows, never which of several objects it holds.

**R2 — The Communication Worker role is required. The JOE implementation is not.**

Communication capability is constitutional. JOE is one replaceable implementation of that
role. The JOE implementation stays optional and must keep supporting degraded operation
under `docs/DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md`. The "No JOE" degraded state stays
valid and stays required.

JOE is not operational truth. JOE is not workflow. JOE is not Mission Records. External
systems are wheels. Dispatch is the truck.

The distinction the walk applies: a constitutional role may be required, and any single
implementation of it may still be replaceable and optional. A finding that says a screen
depends on JOE is only a defect if the screen breaks when JOE is absent.

**R3 — JOE Portal is not the booking workbench.** The booking workbench now sits in the
Pre-Commitment Lifecycle. Per the constitution, Intelligence owns the entire pre-commit
lifecycle, so the workbench belongs to that owner and not to a portal screen.

**R4 — Departments are superseded by agents.** The model is no longer deterministic
separation of process by department name. It is agents. Their Level is not yet determined.

Stop writing "department" in walk findings. Write "agent". Where a screen or a doctrine
file still says department, that wording is a finding, not a fact.

**R5 — Worker constitutions do not replace the deterministic chassis.**

Workers replace organizational departments. They do not replace deterministic mechanisms.
Where deterministic behavior already exists and is governed by doctrine, that behavior
remains exactly as it is.

Intelligence may collect, analyze, evaluate and recommend. Policy-driven scoring remains
reproducible and deterministic. Sorting remains deterministic. Recommendations remain
deterministic where doctrine requires. Decision remains human.

Workers own business responsibilities. The chassis owns deterministic functions. The five
stages in `docs/DISPATCH_DETERMINISTIC_CHASSIS.md` survive the worker model untouched.

A worker boundary and a chassis stage are answers to different questions. Question 1 on
every tab asks who owns the business responsibility. It does not license moving a
deterministic function into a worker.

## Open questions, unresolved

Listed so the walk does not silently pick a side, and so the same question is not
re-argued on twelve separate tabs. Mike resolves these.

**T3 — Agent Level.** R4 leaves Level undetermined. Until it is set, the constitution's
Level 1 through Level 3 numbering describes artifacts, not agent tiers. Do not use the
word Level in a finding to mean an agent tier.

**T4 — Manager already holds the handoff seat.** `docs/MANAGER.md` documents Manager as
dormant and never built, sitting over Intelligence, Library, Publisher and Archive,
receiving their output, presenting it for review, and routing decisions. That is close to
the function the constitution identifies as the missing artifact. The walk must not build
Manager as a side effect of documenting handoffs. Manager's status is Mike's to change.

**T5 — Level 2 partly exists.** The constitution's Level 2 chain runs from opportunity
discovery to archive. `docs/DISPATCH_STATE_TRANSITION_RULES.md` already covers activation
events, atomic human gates, run phases, and transitions that must never happen. Level 2
should be reconciled with that file, not written fresh alongside it.
