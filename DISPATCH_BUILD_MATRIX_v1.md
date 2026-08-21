# DISPATCH_BUILD_MATRIX_v1

**Document Type:** Build Matrix / Mission Register
**Program:** Dispatch
**Owner:** Mike Zachary / Level 1 Transport
**Status:** Active. Missions are authorized individually, never as a block.
**Authority:** Mike Zachary remains final authority (Constitution v3 §3, §22).

**Responds to:** `DISPATCH_REPO_RECONCILIATION_PLAN_v1` — the repository-grounded reconciliation of
the proposed context architecture (DISPATCH_CONTEXT_ARCHITECTURE_PACKAGE_v1, DISPATCH_ONTOLOGY_v1,
MISSION_LAYER / SCHEDULING_LAYER / ORCHESTRATION_LAYER / OUTLOOK_BOUNDARY constitutions,
DRIVER_PORTAL_CONTEXT_v1, and CONTEXT_ARCHITECTURE_REVIEW_STARTUP_SHUTDOWN_RESET_v1_1) against
this repository.

---

## 1. What this document is

The reconciliation produced eleven mission-sized units of work. This document is the register of
those missions: what each one is for, what it may not do, what must be true before it starts, and
what gate it passes through.

It is a **register, not an authorization**. A mission listed here is not approved by being listed.
Each mission is approved individually, in writing, and the approval is recorded verbatim in
`DECISION_LOG.md` before the mission is built — the convention this repository already follows for
every governed capability change.

## 2. Standing constraints on every mission in this register

These are not new rules. They restate constraints already binding under Constitution v3, the
proposed ontology, and the reconciliation's own drift test, so that a builder holding only this
document still holds the fences.

| # | Constraint | Source |
|---|---|---|
| BM-01 | No mission introduces new architecture without review. A new module, table, store, or element is an architectural change and needs its own approval, not just the mission's. | Constitution v3 §11 (No Architecture Drift) |
| BM-02 | No mission reactivates, redesigns, or wires Manager. Manager is dormant, has zero code, and stays that way. | `docs/MANAGER.md`; this mission's standing order |
| BM-03 | No mission creates a second calendar, or presents anything to a driver as a calendar. | OUT-07, D-07, S-07 (proposed); reconciliation C-03 |
| BM-04 | No mission makes Portal a source of truth. Interface surfaces display; the owning element holds. | DRIVER_PORTAL_CONTEXT_v1 D-01 (proposed); Constitution v3 §13 |
| BM-05 | No mission makes the Website or stakeholder view a source of truth. Same rule, external surface. | Same |
| BM-06 | No mission assigns judgment or discretion to a deterministic layer. A deterministic component may evaluate, refuse, and raise. It may never choose between two legitimate options. | DISPATCH_ONTOLOGY_v1 §5 (proposed); Constitution v3 §4, §12 |
| BM-07 | No mission invents doctrine or a business rule. A required rule that does not exist is a stop condition, recorded as a blocker. | Constitution v3 §10 (No Fabrication); ONT-07 (proposed) |
| BM-08 | Every assumption a mission makes is written down in its walkthrough report, named as an assumption, and flagged for Mike's confirmation. | This document |
| BM-09 | A mission that would silently change existing operator-visible behavior brings an enumerated list of what changes to the approval, so the change is approved rather than discovered. | This document |

## 3. Dependency levels

Nothing at a level may begin until everything above it is settled. Level 0 is adjudication by Mike;
it is not work a builder can do.

| Level | Must be settled | By whom |
|---|---|---|
| **0 · Adjudication** | D-1 Orchestration Layer vs Dispatch Spine · D-2 which state machine governs a load · D-3 whether the layer fences apply to existing code | Mike |
| **1 · Defects** | Transition gate bypass · Route Risk durability · duplicate side effects · non-atomic JSON writes | Builder, under the decision-log gate |
| **2 · Read-only foundations** | Trigger inventory · load identity correlation · active-mission definition · session ledger | Builder plans; Mike confirms the definition |
| **3 · Doctrine intake** | Reset protected set · overnight/dormancy rules · operating constants · exception and recovery doctrine | Mike dictates |
| **4 · Capacity and calendar** | Reserve capacity · Jacksonville repositioning · Outlook decision · store authority · the existing calendar page | Mike dictates and decides |
| **5 · Departments and external comms** | COMI and Route Risk contexts · POP doctrine · document retention policy | Mike dictates |

**Level 0 is genuinely blocking for anything that names a layer.** Two governing documents currently
describe the same deterministic machinery under different names: Constitution v3 §6.4 assigns it to
**Dispatch Spine**, specified in `DISPATCH_SPINE_SPECIFICATION_v1` (Claude-3 repo); the proposed
package divides the same responsibilities across three new layers and does not mention the Spine.
Until Mike settles that, a mission that creates "the Mission Layer" as a module is choosing between
two constitutions on his behalf.

Missions M0, M1, M3 and M-A below are written specifically so that they do **not** depend on that
answer: none of them creates, names, or implies a layer. They fix defects in machinery that already
exists under names the repository already uses.

---

## 4. The mission register

Legend — **Gate**: `DL` = DECISION_LOG entry with verbatim approval plus walkthrough report (the
convention for governed capabilities); `WR` = walkthrough report only; `DOC` = document review.

### M0 — Trigger and side-effect inventory

| | |
|---|---|
| **Purpose** | One document listing every place the repository causes a side effect, with its call site, subject, and whether it is guarded. Evidence base for any future trigger registry and for replay safety. |
| **Level** | 2 |
| **Repository area** | Read-only sweep of `dispatch/`, `portal/`, `cin_lite/`, `route_risk/`, `sync/`. |
| **Dependencies** | None. |
| **Files** | One new markdown document. No source file modified. |
| **Explicitly excluded** | Building a registry. Changing any trigger. Proposing which triggers *should* exist. Naming a layer. |
| **Acceptance** | Every notification send, every record-creation-triggered-by-another-record, and every status cascade appears once with a `file:line` citation. Re-running the sweep finds no additions. |
| **Regression risk** | None — no code changes. |
| **Doctrine dependencies** | None. |
| **Gate** | DOC |
| **Builder lane** | Dispatch repo, single builder, one pass. |

### M1 — Mission state transition gate closure

| | |
|---|---|
| **Purpose** | Make the transition table that already exists in the code actually govern the milestone path, so a load cannot skip states, and raise a Conflict Notice on refusal instead of a bare exception. |
| **Level** | 1 |
| **Repository area** | `dispatch/services.py` (`add_milestone`), `portal/models/conflict.py` (one new notice type). |
| **Dependencies** | None. Deliberately independent of D-2: it changes no status and adds none. |
| **Files** | `dispatch/services.py`, `portal/models/conflict.py`, new + existing tests. |
| **Explicitly excluded** | Adding, removing or renaming any status. Adding evidence requirements to any transition. Touching the archive path (already gated). Creating a Mission Layer module. Changing the transition table itself. |
| **Acceptance** | An out-of-order milestone is refused, leaves the load unchanged, records nothing, and raises exactly one notice; a full ladder walk succeeds unchanged; `checkpoint` milestones still record with no status change; the whole existing suite passes with skipping test helpers rewritten, not deleted. |
| **Regression risk** | **High and concentrated** — any caller that jumps states starts failing. BM-09 applies: the enumerated list of newly-refused paths goes to Mike with the approval. |
| **Doctrine dependencies** | None new. The table is already in the code and already in use. |
| **Gate** | DL |
| **Builder lane** | Dispatch repo, single builder. Not parallel with M2. |

### M2 — Transition evidence record

| | |
|---|---|
| **Purpose** | Record for every accepted transition what changed, when, on whose authority, and on what evidence — with *absent* a permanent, legitimate value that never blocks the transition. |
| **Level** | 2 |
| **Dependencies** | M1. **D-2** if the transition set is to be re-derived from the Spine or the proposed constitution. |
| **Explicitly excluded** | Requiring evidence for any transition (a doctrine decision). Reading position from anything. Any ELD work. Back-filling existing loads. |
| **Regression risk** | Low — additive. Follow the existing idempotent `ALTER TABLE` migration pattern (`dispatch/db.py`), not a base-schema edit. |
| **Doctrine dependencies** | M-04 adoption (absent-is-permanent). |
| **Gate** | DL |
| **Status** | **Held.** New table = architectural change under BM-01; needs its own approval. |

### M3 — Route Risk durability

| | |
|---|---|
| **Purpose** | Stop a process restart from destroying operational records. Persist Route Risk events to the `route_risk_events` table that already exists in the schema and is never written. |
| **Level** | 1 |
| **Repository area** | `route_risk/engine.py`, `dispatch/route_risk.py`, `dispatch/store.py`, existing table at `dispatch/db.py`. |
| **Dependencies** | None for durability. **B-09** (Route Risk context) for retention and lifecycle — deliberately out of scope. |
| **Explicitly excluded** | External feeds of any kind. Changing consequence thresholds or COMI evaluation. Automatic notification. Deciding whether Route Risk collects or receives its feeds. Adding a table (the table exists). |
| **Acceptance** | An event recorded before a restart is readable after it; the standalone engine still imports and runs with no Dispatch dependency; in-memory behavior is preserved exactly when no store is injected. |
| **Regression risk** | Medium — `route_risk/` is deliberately decoupled and must stay standalone. Persistence is **injected**, never imported, following the module's existing `comi_eval_fn` pattern. |
| **Doctrine dependencies** | None for the fix. B-04 to classify the result in the protected-state map. |
| **Gate** | DL — this changes a state class in the protected-state map. |
| **Builder lane** | Dispatch repo, single builder. Parallel with M1. |

### M-A — Atomic JSON store writes

| | |
|---|---|
| **Purpose** | A power-off mid-write can currently truncate a JSON store; two concurrent writers can lose an update. Replace read-modify-write `write_text()` with write-temp-then-`os.replace()` across the portal stores. |
| **Level** | 1 |
| **Repository area** | The eleven `portal/models/*.py` stores and `dispatch/email_helper.py`. |
| **Dependencies** | None. |
| **Explicitly excluded** | Changing any store's schema, contents, or read path. Adding locking (a separate, larger question). Migrating anything. Changing where any store lives. |
| **Acceptance** | Every store's save path is atomic on POSIX and Windows; a simulated failure mid-write leaves the previous file intact and readable; no store's data shape changes; whole suite passes. |
| **Regression risk** | Low — mechanical, behavior-preserving. The one real risk is a temp file left behind on failure, which the tests must cover. |
| **Doctrine dependencies** | None. |
| **Gate** | DL |
| **Builder lane** | Dispatch repo, single builder. Parallel with M1 and M3. |

### M4 — Load identity correlation

| | |
|---|---|
| **Purpose** | Make "show me everything about this load" answerable across the sandbox, freight and contract boundaries — without renaming an identifier or migrating a record. |
| **Level** | 2 |
| **Dependencies** | **D-15** — does M-01 mean one identifier, or one answerable retrieval? This mission implements the second reading only. |
| **Explicitly excluded** | Any change to `_gen_id`, `make_id`, or sandbox ids. Any migration. Any write path. Any new identifier. |
| **Gate** | WR, or DL if it touches archive reads. |
| **Status** | **Held** pending D-15. |

### M5 — Execution ledger and replay guard

| | |
|---|---|
| **Purpose** | Generalize the five guards the repository already has into one append-only ledger keyed by trigger, subject and occurrence, written before the side effect and checked before every attempt. |
| **Level** | 1 |
| **Dependencies** | M0 for the complete call-site list. **Level 0** for where the ledger lives and what it is called. |
| **Explicitly excluded** | Any scheduler. Any retry policy. Halt-and-raise semantics (**D-14**). Changing what any notification says. |
| **Regression risk** | Medium. Tests must assert on the ledger, never the outbox — the outbox filename is deterministic and overwrites, so an outbox assertion passes even when two real sends occurred. |
| **Gate** | DL |
| **Status** | **Held.** New module + new store = architectural change under BM-01. Must precede anything scheduled. |

### M6 — Session ledger, device-scoped

| | |
|---|---|
| **Purpose** | Give the system something to open and close: one record per device session, with no business effect whatsoever. |
| **Level** | 2 |
| **Explicitly excluded** | **Pausing anything.** Any effect on any workflow. Any server-side consequence. Any coupling between two devices' sessions. Blocking logout for any reason. |
| **Regression risk** | Low. The real risk is scope creep into "paused" semantics — an undefined state with no owner and no exit condition. The exclusion list is this mission's most important section. |
| **Gate** | WR |
| **Status** | **Held.** New state class = architectural change under BM-01. |

### M7 — Session-open reconciliation report, read-only

| | |
|---|---|
| **Purpose** | The buildable core of startup: read what is authoritative, compare against what the local instance last saw, present one list of what changed while the session was closed. Writes nothing, decides nothing. |
| **Dependencies** | M3, M5, M6, **D-6** (active mission), **D-7** (store authority). |
| **Explicitly excluded** | Reading Outlook (**D-4**). Rebuilding any display — they rebuild themselves. Preloading Library. Resuming any sequence. Writing anything at all. |
| **Status** | **Held.** |

### M8 — Session-close promotion sweep

| | |
|---|---|
| **Purpose** | Find work that exists on the device and nowhere authoritative; hand each item to its owning element, or raise a card. Never save on the surface; never block the close. |
| **Dependencies** | M6, M-A. |
| **Explicitly excluded** | Marking anything paused. Any server-side signal. Transitioning a mission on the driver's behalf. Blocking the close for any reason. Purging anything. |
| **Status** | **Held.** |

### M9 — Operating constants register

| | |
|---|---|
| **Purpose** | One governed source for every operating constant, with dependent modules named beside each value. |
| **Dependencies** | **D-13** — Mike states the true values. Two live discrepancies exist (operating radius 500 in code vs 250–260 in the corpus; card threshold 90 in config vs 85 in the corpus) and must be resolved, never averaged or guessed. |
| **Explicitly excluded** | Changing any scoring formula. Guessing any value. Introducing a constant not already in use. |
| **Status** | **Blocked** — doctrine (BM-07). |

### M10 — Capacity projection, read-only

| | |
|---|---|
| **Purpose** | The first genuine piece of a Scheduling Layer: a derived, disposable projection of committed time, and a feasibility verdict evaluated against doctrine. Advises; never decides; writes no calendar. |
| **Dependencies** | **D-8** reserve capacity, **D-9** repositioning, **D-4** Outlook, **D-5** the existing calendar page, M9. Every one is Mike's. |
| **Explicitly excluded** | Writing any calendar event. Blocking any booking. Presenting anything as a calendar (BM-03). Amending doctrine to resolve a conflict. |
| **Status** | **Blocked** — doctrine (BM-07). |

---

## 5. Authorized in this pass

| Mission | Level | Why it is safe to build now |
|---|---|---|
| **M0** | 2 | Documentation only. No code, no architecture, no doctrine. |
| **M1** | 1 | Enforces a table already present and already in use. Creates no layer, no status, no store. |
| **M3** | 1 | Writes to a table already in the schema. Persistence injected, not imported; standalone contract preserved. |
| **M-A** | 1 | Mechanical durability fix. No schema, no behavior, no new component. |

Every other mission in this register is **held or blocked** — either on a Level 0 adjudication, on
doctrine Mike has not yet dictated, or on BM-01 because it would introduce a new component.

## 6. Amendment

This register is amended only by Mike, in writing. A mission may not be widened after approval; a
mission that turns out to need more than its stated scope stops and returns for a new approval.
