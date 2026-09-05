# DISPATCH_BUILD_MATRIX_v2

**Document Type:** Build Matrix / Mission Register
**Program:** Dispatch
**Owner:** Mike Zachary / Level 1 Transport
**Supersedes:** `DISPATCH_BUILD_MATRIX_v1` — revised to reflect the architectural adjudication of 2026-08-21.
**Status:** Active. Missions are authorized individually, never as a block.
**Authority:** Mike Zachary remains final authority.

---

## 1. What changed from v1

The adjudication resolved the Level 0 blocker that held most of v1's register.

| v1 said | v2 says |
|---|---|
| Level 0 adjudication (Spine vs layers) blocks everything naming a layer | **Resolved.** Spine remains the element; Mission, Scheduling, Orchestration are ownership partitions inside it. Missions may now name a partition. |
| State model undecided — three candidates | **Resolved.** Two models, different subjects, coexisting. No third authority. |
| Load identity — one identifier or one retrieval, undecided | **Resolved.** One answerable retrieval chain. No migration authorized. |
| Driver-First doctrine absent | **Drafted as v2**, pending numbering approval |
| M2, M5, M6 held under BM-01 (new architecture) | **Unblocked in principle** — a partition-scoped component is no longer "new architecture", it is Spine implementation. Still requires individual approval. |
| Four corrective items scattered across findings | **Registered as C1–C4**, explicitly not to be combined |

## 2. Standing constraints — unchanged from v1, plus three

| # | Constraint |
|---|---|
| BM-01 | No mission introduces new architecture without review. A component inside an adjudicated Spine partition is Spine implementation, not new architecture — but still needs its own approval. |
| BM-02 | No mission reactivates, redesigns, or wires Manager. |
| BM-03 | No mission creates a second calendar, or presents anything to a driver as a calendar. |
| BM-04 | No mission makes Portal a source of truth. |
| BM-05 | No mission makes the Website or stakeholder view a source of truth. |
| BM-06 | No mission assigns judgment or discretion to a deterministic partition. Evaluate, refuse, raise — never choose between two legitimate options. |
| BM-07 | No mission invents doctrine or a business rule. |
| BM-08 | Every assumption is written down in the walkthrough report and flagged for Mike. |
| BM-09 | A mission that changes existing operator-visible behavior brings an enumerated list of what changes to the approval. |
| **BM-10** | **No mission may merge the load-status and work-item state models, replace either, or create a third state authority.** (Decision 2) |
| **BM-11** | **No identifier migration.** Correlation only. (Decision 3) |
| **BM-12** | **No scheduler or overnight worker may be implemented** under the provisional overnight boundary. Planning only. (Decision 7) |

## 3. Completed

| Mission | Result |
|---|---|
| **M0** Trigger and side-effect inventory | 32 call sites documented; 0 time-based. `DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1` |
| **M1** Mission state transition gate closure | Milestone path now gated; 90 of 121 pairs refused; 28 tests |
| **M3** Route Risk durability | Persisted; survives a real two-process restart; 20 tests |
| **M-A** Atomic JSON store writes | 12 stores; crash-safety proven; 18 tests |

Suite: **2771 passing**, from a 2705 baseline.

## 4. Corrective missions — C1 to C4

Registered per Decision 6 as **bounded corrective missions, not architectural redesign**.
**Explicitly not to be combined.**

### C1 · Retire the duplicate sandbox mission-state copy
| | |
|---|---|
| **Defect** | The load's status is copied into `sandbox.card_data.engine_status` — a second stored copy of mission state, in a second store, written by an explicit sync-back call. Violates Driver-First D4 ("One Mission State") and the Spine/Mission source-of-truth policy. |
| **Evidence** | `portal/models/sandbox.py:231-240`; called at `portal/routes/pages.py:991` and `portal/routes/api.py:509` |
| **Approach** | Approved read-through design: the sandbox entry keeps `engine_load_id` (a correlation key, which BM-11 preserves) and reads status through it. |
| **Excluded** | Removing `engine_load_id`. Any identifier change. Any change to the sandbox lifecycle or HOLD sweep. Touching the load status model. |
| **Acceptance** | No stored copy of load status outside `loads.status`; every surface that displayed it still displays it; a structural test forbids reintroduction. |
| **Regression risk** | Medium — two display paths read the copy today. |
| **Gate** | DECISION_LOG + walkthrough report |

### C2 · Reconcile or retire `/calendar`
| | |
|---|---|
| **Defect** | `/calendar` renders a month grid from Dispatch's own load records and sits in the main navigation. Outlook must be the only calendar; the Driver Portal presents a Visual Capacity Board. Violates Driver-First D4 ("One Calendar"). |
| **Evidence** | `portal/routes/pages.py:310`; `dispatch/services.py:1899`; `portal/templates/calendar.html`; `portal/templates/base.html` navigation |
| **Blocked by** | **The Visual Capacity Board cannot be built** — it displays capacity, and capacity is blocked on Reserve Capacity Doctrine. |
| **Therefore** | C2 splits. **C2a (available now):** retire or rename the page so nothing is presented as a calendar. **C2b (blocked):** build the Visual Capacity Board. C2a must not silently become C2b. |
| **Excluded** | Any Outlook integration. Any capacity computation. |
| **Decision required** | Retire outright, or rename to a non-calendar operational view pending C2b? |
| **Gate** | DECISION_LOG + walkthrough report |

### C3 · Correct the status-change audit asymmetry
| | |
|---|---|
| **Defect** | `services.update_load()` validates the transition **and** writes a `status_change` activity recording old → new. `add_milestone()` validates (since M1) but writes status via `store.update_load()` and records **no activity**. Two paths change status; one leaves an audit trail. Spine §8 requires every meaningful activity to create an event with `previous_state` and `new_state`. |
| **Evidence** | `dispatch/services.py:189-201` (audited) vs the M1 gate path (unaudited); `activities` table at `dispatch/db.py:177` |
| **Excluded** | Introducing the Spine Event schema wholesale — that is a separate, larger mission. This closes the asymmetry using the mechanism already present. |
| **Acceptance** | Every status change writes exactly one activity regardless of path; no duplicate activity when both paths are involved; existing activity consumers unaffected. |
| **Regression risk** | Low — additive. Watch for double-writing. |
| **Gate** | DECISION_LOG + walkthrough report |

### C4 · Continue replay-protection work
| | |
|---|---|
| **Purpose** | 8 mechanisms guard 14 call sites; **15 remain unguarded**, including duplicate stall notifications and duplicate checkpoint emails. Decision 6 requires this to continue **before** unattended scheduled operations are authorized. |
| **Evidence** | `DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1` §8 |
| **Owner** | Spine/Orchestration |
| **Excluded** | Any scheduler (BM-12). Any retry policy. Halt-and-raise semantics — that posture question is undecided. |
| **Acceptance** | Each guarded effect invoked twice produces one effect and one ledger entry; the ledger survives restart; **tests assert on the ledger, never the outbox** — the outbox filename is deterministic and overwrites, so an outbox assertion passes even when two real sends occurred. |
| **Gate** | DECISION_LOG + walkthrough report |

## 5. Newly unblocked by the adjudication

These were held in v1 under BM-01 as "new architecture". A component inside an adjudicated Spine
partition is now Spine implementation. **Each still requires individual approval.**

| Mission | Partition | Newly available because | Remaining dependency |
|---|---|---|---|
| **M2** Transition evidence record | Spine/Mission | Partition ownership settled; state model settled (BM-10) | Fable's evidence requirements must be **mapped into** the load-status model, never made a third model |
| **M5** Execution ledger / replay guard | Spine/Orchestration | Ownership settled — this is C4's mechanism | M0 (done) |
| **M6** Session ledger, device-scoped | Spine/Orchestration | Ownership settled | Must have **no business effect**; must not introduce a "paused" state |
| **M4** Load identity correlation | Spine/Mission | **Decision 3 settles the reading** — retrieval chain, not migration | BM-11: no identifier change |

## 6. Still blocked

| Mission | Blocked by | Kind |
|---|---|---|
| **M7** Session-open reconciliation report | Active-mission definition; VPS/local store authority | Decision |
| **M8** Session-close promotion sweep | M6 | Sequence |
| **M9** Operating constants register | True constant values. Two live discrepancies: radius 500 in code vs 250–260 in corpus; card threshold 90 in config vs 85 in corpus | Doctrine |
| **M10** Capacity projection | **Reserve Capacity Doctrine** and **Jacksonville Repositioning Doctrine** | Doctrine — hard |
| **C2b** Visual Capacity Board | Same as M10 | Doctrine — hard |
| Outlook integration, either role | Integration decision not made | Decision |
| Reset function | Protected set drafted and complete; not adopted | Doctrine |
| Any scheduler / overnight worker | BM-12 and Overnight Operations Doctrine | Doctrine + standing bar |
| Driver-First citation prefixing | Numbering approval (Decision 4.5 bars code change until then) | Sequence |

## 7. Recommended first executable mission

### C3 · Status-change audit asymmetry

**Why this one.**

- **Needs no doctrine.** The `activities` mechanism, the `status_change` type and the audited path
  all already exist. C3 makes the second path match the first.
- **Needs no decision.** C1 needs a read-through design choice; C2 needs retire-or-rename; C4 needs
  the ledger's shape settled. C3 has one obviously correct outcome: both paths audit.
- **Smallest blast radius of the four.** Additive. No display changes, no store changes, no
  identifier changes, no behavior visible to an operator — so BM-09's enumerated-change burden is
  nearly empty.
- **It is a direct Spine §8 compliance fix**, the first work performed under the adjudicated
  partition model, which makes it a low-risk proof that the partition vocabulary works in practice
  before anything larger is attempted.
- **It closes a gap M1 exposed.** M1 fixed validation and left audit visibly asymmetric; C3 finishes
  what M1 started, while the reasoning is still fresh and the tests are still recent.

**Sequence after C3:** C1 (needs one design decision) → C4/M5 (must precede anything unattended) →
C2a (needs one retire-or-rename decision) → M4/M2/M6 as approved.

**Not recommended first:** C4, despite being the precondition for overnight work — it is the largest
of the four, and its acceptance criteria depend on where the ledger lives, which is worth settling
against a smaller mission first.

## 8. Amendment

Amended only by Mike Zachary. A mission may not be widened after approval; a mission needing more
than its stated scope stops and returns for a new approval.
