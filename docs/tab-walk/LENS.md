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

**R2 — JOE is no longer optional.** This supersedes the JOE optionality language in
`docs/DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md` and
`docs/DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md`. See T1 below for what it leaves open.

**R3 — JOE Portal is not the booking workbench.** The booking workbench now sits in the
Pre-Commitment Lifecycle. Per the constitution, Intelligence owns the entire pre-commit
lifecycle, so the workbench belongs to that owner and not to a portal screen.

**R4 — Departments are superseded by agents.** The model is no longer deterministic
separation of process by department name. It is agents. Their Level is not yet determined.

Stop writing "department" in walk findings. Write "agent". Where a screen or a doctrine
file still says department, that wording is a finding, not a fact.

## Open questions, unresolved

Listed so the walk does not silently pick a side, and so the same question is not
re-argued on twelve separate tabs. Mike resolves these.

**T1 — What JOE being required does to independence.** `DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md`
lists JOE under what Dispatch borrows, and names "No JOE" as one of the designed degraded
states. R2 makes JOE required. Two readings follow and they lead different places. Either
JOE moves from borrowed to owned, and Dispatch must then contain that capability itself,
or JOE stays borrowed and Dispatch no longer runs complete without it. The second reading
contradicts the standing rule that Dispatch remains complete and operational without
optional plug-ins. Degraded mode needs a new answer for the JOE row either way.

**T2 — Which stages an agent may occupy.** `DISPATCH_DETERMINISTIC_CHASSIS.md` holds that
the engine is deterministic and that five stages never collapse: filter, score, sort,
recommendation, decision. It states that decision may not be produced by the engine. R4
replaces deterministic department separation with agents. The boundary that must survive
is that no agent produces a decision. Which of the other four stages an agent may occupy,
and whether an agent-produced score still has to reproduce from the record and the profile
alone, is undetermined.

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
