# Manager — Reserved Capability

**STATUS: DORMANT / RESERVED CAPABILITY / NOT IMPLEMENTED**

This document is the permanent architectural record for "Manager" — a capability named in
Dispatch's tri-department reconciliation planning but never built. It exists so Manager stays
visible as a recognized part of Dispatch's architecture without being active in it.

**This document authorizes no code, no route, no data model, and no runtime behavior. Manager
does not participate in runtime operation. Manager does not own data.** It is documentation only.

Decided by Mike, recorded here on `dispatch/canonical-reconciliation-integration`.

---

## 1. What Manager Is (Doctrine)

Manager was named in `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1` (Section 8,
Final Recommendation) as the eventual consumer/orchestrator sitting over Intelligence, Library,
Publisher, and Archive, once their object flow is wired — declared explicitly "not ready for
full build" at that time, with the direction: "first map tri-department objects into existing
Work Item/Card/Conflict Notice surfaces."

The tri-department shared object contracts name one object under Manager's authority:
**Manager Decision Support Note** — drafted by Intelligence, routed by Manager, carrying a fixed
closing statement ("This is a recommendation only. No action is authorized. Mike decides.") and
a `consequence_level` (0-5). No other object is Manager-owned in the contract set; Manager's role
throughout is routing and review, never data ownership or final decision authority.

**Operating model**: Manager receives findings/candidates/requirements from the departments,
presents them for human review, and routes decisions — it does not decide anything itself.

**Authority model**: Manager has no approval authority of its own. Every object that passes
through it either requires human decision (per its `decision_needed` flag) or is informational.
This is consistent with the Constitution's standing rule that AI decides nothing and Mike is
final authority — Manager, if built, would be a routing/visibility layer, never a decision-maker.

**Relationship model**: Manager sits downstream of Intelligence, Library, and Publisher, and
upstream of Portal's presentation surfaces (Card, Work Item, History). It was never scoped to
own Archive, Library truth, or Publisher approval — those stay with their respective departments
regardless of whether Manager is ever built.

## 2. Current Implementation Status: Zero Code

A repo-wide investigation (`MANAGER_ORCHESTRATION_REVIEW_v1`, Phase 1) found no Manager code of
any kind anywhere in Dispatch: no class, module, blueprint, route, or template. The only two
hits from a case-insensitive "manager" search across the entire codebase are Python's own
`contextlib.contextmanager` (unrelated) and a plain-English checklist string inside a cin_lite
workflow ("assign proposal manager") — a human task-list label, not a system.

What exists instead, each owned separately by its own department, with no shared orchestration
layer over them: Sandbox's freight/SAM opportunity cards, Publisher's own action queue,
`cin_lite`'s pipeline/queue views, and Conflict Notices (`portal/models/conflict.py`) — a real,
working, `sandbox_id`-keyed conflict-tracking store with its own create/resolve lifecycle.

## 3. Why Manager Remains Unimplemented — This Decision

A follow-up investigation (Phase 2) found that Manager has not yet proven it requires runtime
implementation:

- Ownership boundaries across departments are becoming clearer through the completeness review
  cycle (Publisher, Library, Intelligence reviews), independent of Manager existing.
- Approval chains are becoming clearer (the Library/Publisher/Archive approval gates already
  built).
- Inter-department relationships are becoming clearer through the Stage 6 object-flow trace.
- Existing systems already perform much of the deterministic routing once assumed to require
  Manager — notably, `portal/models/conflict.py` already has partial, unrealized
  cross-department type vocabulary (`publisher_missing_document`, `library_missing_asset`), with
  a real generator function for the latter that exists and is tested but is never called from any
  live route.

Given this, the architectural decision is: **Manager remains on the roster, designated dormant.**
Not built. Not deleted. Not refactored into another subsystem. Not started as an implementation
mission. It re-enters consideration only if future evidence demonstrates an operational need —
see Section 5.

## 4. Design Findings On Record (Phase 2 — For Whenever Implementation Is Reconsidered)

If and when Manager implementation is authorized in the future, these findings — already
established, not to be re-derived from scratch — should be the starting point:

1. **Read-composition, not new storage, is the lower-risk starting hypothesis.** New storage
   would make Manager a new source of truth, which the canonical matrix explicitly deferred.
   A read-composition layer (mirroring `reconciliation/adapters/*.py`'s deliberately read-only
   design) would let Manager exist without inventing new authoritative state or IDs.
2. **A "Work Item" is best scoped narrowly at first** — a reference wrapper around records that
   already exist and are reachable (Publisher actions, Conflict Notices, Sandbox cards), not a
   general cross-department object, since Library candidates are unreached and Intelligence has
   no distinct sub-object types to wrap yet.
3. **An approval gate is only needed if Manager gains mutating state of its own** — not needed
   under a read-composition-only design.
4. **Some of this work may already be the same task as Portal's own presentation-layer
   consolidation problem** — Stage 6's object-flow trace found Portal already fragments
   "History"/"queue"/"Card" concepts across three unrelated views on one page. Unifying those was
   independently described as "a presentation-layer consolidation, not a new data-flow" — which
   may not require a "Manager" concept at all, only a shared rendering layer.
5. **Manager should compose over Conflict Notices, not subsume it** — Conflict Notices has its
   own working create/resolve lifecycle and UI already; rebuilding it inside Manager would waste
   working code.
6. **Sandbox's card concept does not generalize** — it's tightly coupled to freight-specific
   fields (deadhead miles, fuel estimate, engine load linkage). Any future Manager-level "card"
   would need to be a distinct, third concept, not a retrofit of `sandbox.py`.

## 5. Activation Criteria — What Would Need To Be True

Not a commitment to build; a record of what evidence would make this worth reconsidering:

- Stage 6 object-flow links that remain unresolved (per `DISPATCH_STAGE6_OBJECT_FLOW_SCOPING_v1`
  — Links 1, 3, 5, 6, 9) reach a state where departments produce canonical, ID-referenceable
  objects for a composition layer to unify.
- A demonstrated operational problem from the current fragmentation (three parallel card/queue/
  history views, confirmed in Stage 6 Link 10) serious enough — a real usability or governance
  cost, not a hypothetical one — to justify consolidation work.
- Explicit authorization from Mike to begin even the narrow, read-composition-only version
  scoped in Section 4, above.

## 6. Related Missions And Documents

The following live in the `jax1313-outlook/Claude-3` build-tracking repository, not in Dispatch
itself, and are the source material this document consolidates:

- `MANAGER_ORCHESTRATION_REVIEW_v1.md` — Phases 1 and 2, full evidence and reasoning behind
  Sections 2-4 above.
- `DISPATCH_INTEGRATION_BRIDGE_INVESTIGATION_v1.md` — named Manager Orchestration Review as the
  most critical hard blocker on Integration Bridge planning; this decision resolves that blocker
  by declaring Manager dormant rather than by building it.
- `DISPATCH_STAGE6_OBJECT_FLOW_SCOPING_v1.md` — the object-flow evidence underlying Section 5's
  activation criteria.
- `DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md` — Section 8, Manager's original
  doctrinal naming and deferral.

## 7. Historical Decision Record

| Date/Session | Decision |
|---|---|
| Canonical matrix (Section 8) | Manager named as a future capability; declared "not ready for full build." |
| Manager Orchestration Review, Phase 1 | Confirmed zero Manager code exists anywhere in Dispatch. |
| Manager Orchestration Review, Phase 2 | Scoped six open design questions; found Manager less blocked than assumed, but did not authorize building it. |
| This document | **Manager Preservation Decision**: dormant, reserved, not implemented. Not built, not deleted, not refactored. Documented and made visible in Dispatch's own repository structure, separate from and in addition to the Claude-3 planning record. |

Mike decides.
