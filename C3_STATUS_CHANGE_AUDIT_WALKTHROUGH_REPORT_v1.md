# C3_STATUS_CHANGE_AUDIT_WALKTHROUGH_REPORT_v1

## Status-Change Audit Symmetry

**Status:** Implemented and verified. Branch: `claude/dispatch-repo-context-reconcile-7mblbb`.

**Mission:** C3 of `DISPATCH_BUILD_MATRIX_v2` — bounded corrective mission, Decision 6.3 of the
architectural adjudication of 2026-08-21.

**Owner (adjudicated):** Spine/Mission — *where does this load stand, and what evidence supports
that standing?* An audit event is that evidence.

---

## 1. Required analysis, performed before editing

### 1.1 Every path capable of changing load status

Searched by symbol (`update_load`, `UPDATE loads`) across `dispatch/`, `portal/` and `cin_lite/`.
**Four service paths, plus the raw store layer beneath them.**

| # | Path | Validates? | Audited before C3? |
|---|---|---|---|
| 1 | `services.update_load()` (`:180`) | Yes | **Yes** |
| 2 | `services.add_milestone()` (`:468`) | Yes, since M1 | **No** |
| 3 | `services._try_auto_dispatch()` (`:284`) | No — guarded by a `status != "created"` precondition that makes an illegal transition unreachable | **No** |
| 4 | `services.archive_load()` (`:839`) | Yes | **No** |
| — | `store.update_load()` (`dispatch/store.py:151`) | No — raw write by design | No, and deliberately still not |

**The mission brief named paths 1 and 2. Paths 3 and 4 were found by this analysis.** They are
included because the required outcome is *"every accepted status change, **regardless of approved
entry path**"* — and a load moving `completed → archived` with no audit trail is the same defect the
mission exists to correct.

No route, template or other module writes `loads.status` outside these paths. The only other
`UPDATE loads` statements in the repository are in test fixtures adjusting `created_at`.

### 1.2 Which paths produced status_change events — measured, not read

Probed against a throwaway database before any edit:

```
A) after create_load              : []                       <- correct, no transition
B) update_load created->dispatched: 1 event                  <- the reference behavior
C) update_load NO-OP disp->disp   : 2 events                 <- writes an event for a no-op
D) add_milestone (status moved)   : still 2                  <- THE DEFECT
E) after 4 more milestones        : still 2                  <- milestone path audits nothing
F) refused milestone              : []                       <- already correct
G) auto-dispatch created->disp    : []                       <- second unaudited path
H) archive_load completed->archived: []                      <- third unaudited path
```

### 1.3 Can any current path create duplicate audit events?

**No, and C3 introduces none.** Paths 2, 3 and 4 all write through `store.update_load()` — the raw
layer — never through `services.update_load()`. No path chains into another, so a single status
change cannot produce two events. `assign_driver()` → `_try_auto_dispatch()` is the only chain, and
it changes status once. A regression test holds this (`test_no_path_chains_into_another`).

### 1.4 The narrowest implementation point

`store.update_load()` is the single point every path passes through, and was rejected. Two reasons,
the second decisive:

1. It is deliberately the raw, unvalidated write. M1 established this and
   `tests/test_milestone_transition_gate.py::test_store_update_load_itself_is_still_unvalidated`
   asserts it. Adding behavior there changes its contract.
2. **It cannot satisfy the audit requirement.** The mission requires recording the *originating
   operation*. The store layer cannot know whether it was called by a milestone, an archive, or a
   direct update. Only the service call sites know.

**Chosen: one helper in the service layer, called from four sites.** This is the narrowest point
that can record everything required.

### 1.5 Transaction and error behavior

Unchanged. The audit write was already a separate transaction from the status write (each
`store.*` call opens its own connection), and remains so. No call site's exception behavior changed:
`update_load()` still raises on an invalid transition before writing anything; `add_milestone()`
still returns its refusal marker; `archive_load()` still raises on an already-archived load.

---

## 2. What changed

**One file: `dispatch/services.py`.**

1. **`_record_status_change()`** — new helper. Writes exactly one `status_change` activity.
   Deliberately contains **no** no-op filtering: whether a no-op deserves an event is decided by the
   caller (see §5).
2. **`update_load()`** — same trigger condition as before, now routed through the helper. Behavior
   preserved exactly, **including the no-op event**.
3. **`add_milestone()`** — audits inside the accepted branch, guarded on a real change.
4. **`_try_auto_dispatch()`** — audits `created → dispatched`. Previous state is known from the
   guard above it, not re-read.
5. **`archive_load()`** — audits `<previous> → archived`.
6. **Import** — `LoadActivity` moved to the module-level import block (it was imported inline).

**No schema change. No new table, column or store.** The existing `activities` table carries it.

### Fields recorded

| Requirement | Where it lands |
|---|---|
| load identifier | `load_id` |
| previous state · new state | `message` — the format this repository already used |
| originating operation | `message` suffix, `(via …)` |
| timestamp, repository convention | `created_at`, via `_utc_now()` → `YYYY-MM-DDTHH:MM:SSZ` |
| initiating actor / actor context | `author`, and `source="user"` when an actor is known |

**Actor is never fabricated.** Only `add_milestone()` carries one (`entered_by`); it also records
the milestone's own source in the operation string. The other three paths pass nothing and record
`source="system"` with an empty author — which is exactly what the audited path already did.

---

## 3. Before and after

| Path | Before | After |
|---|---|---|
| `update_load()` real change | `Status changed from created to dispatched` | `Status changed from created to dispatched (via load update)` |
| `update_load()` no-op | `Status changed from dispatched to dispatched` | `Status changed from dispatched to dispatched (via load update)` — **preserved** |
| `add_milestone()` real change | *(nothing)* | `Status changed from at_pickup to picked_up (via milestone 'loaded' from driver)`, `author="Mike"` |
| `add_milestone()` same-status sibling | *(nothing)* | *(nothing)* — deliberate, §5 |
| `add_milestone()` refused | *(nothing)* | *(nothing)* — unchanged |
| `_try_auto_dispatch()` | *(nothing)* | `Status changed from created to dispatched (via auto-dispatch)` |
| `archive_load()` | *(nothing)* | `Status changed from completed to archived (via archive)` |

Verified live — a full ladder now produces one event per transition, in order, with no gaps:

```
Status changed from created to dispatched (via milestone 'dispatched' from dispatcher)
Status changed from dispatched to en_route_pickup (via milestone 'en_route_pickup' from dispatcher)
Status changed from en_route_pickup to at_pickup (via milestone 'arrived_pickup' from dispatcher)
Status changed from at_pickup to picked_up (via milestone 'loaded' from dispatcher)
Status changed from picked_up to in_transit (via milestone 'departed_pickup' from dispatcher)
Status changed from in_transit to at_delivery (via milestone 'arrived_delivery' from dispatcher)
Status changed from at_delivery to delivered (via milestone 'delivered' from dispatcher)
Status changed from delivered to completed (via milestone 'completed' from dispatcher)
Status changed from completed to archived (via archive)
```

### Operator-visible change (BM-09)

One: **every `status_change` message now carries a `(via …)` suffix.** These messages render on the
load detail and read-only detail pages. The change is additive — no existing text was removed — and
every existing test asserting on message content uses substring matching, so none broke.

---

## 4. Assumptions (BM-08)

1. **The existing `activities` shape is the "approved repository equivalent"** for previous state,
   new state and originating operation. They are recorded in prose, as this repository has always
   recorded them, rather than in new structured columns. Adding columns would be a schema change
   under BM-01 and beyond "narrowest implementation point". **Spine §8 wants structured
   `previous_state` / `new_state` fields** — that is the Spine Event-schema mission, which C3 was
   explicitly not authorized to begin. Recorded as unresolved (§5).
2. **`source="user"` when an actor is known, `"system"` otherwise.** `LoadActivity.source` is
   validated against `ACTIVITY_SOURCES = ["user", "system"]`, so a milestone's own source vocabulary
   (`driver`, `dispatcher`, `eld`, …) cannot go in that field. It is preserved in the operation
   string instead, so nothing is lost and nothing is invented.
3. **`archive_load()`'s previous state is read from the `load` fetched at the top of the function.**
   Nothing between that read and the status write changes status.
4. **Paths 3 and 4 are in scope** despite not being named in the brief, on the strength of
   "regardless of approved entry path". If Mike intended a strictly two-path fix, the auto-dispatch
   and archive call sites are two lines each and trivially removable.

---

## 5. Unresolved issues

### 5.1 The no-op divergence — deliberately not resolved

`update_load()` writes an audit event when previous == new, producing
`Status changed from dispatched to dispatched`. That is a **false statement in an audit log**, and
it predates C3.

The mission said: *"A no-op write where previous_state equals new_state must follow existing
repository policy. Do not invent new policy without identifying the current behavior first."*

Current behavior is now identified (§1.2 line C). **C3 preserved it** rather than changing it —
changing it would have altered existing policy, which this mission did not authorize. The three
paths C3 added fire only on a real change, because for new code there was no existing policy to
follow and recording a non-change as a change would be wrong on a path where same-status milestones
are routine (`departed_pickup` and `in_transit` both map to `in_transit`; `delivered` and
`pod_received` both map to `delivered`).

**Result: a residual inconsistency.** A no-op through `update_load()` is audited; a no-op through a
milestone is not. Both behaviors are asserted by tests (`TestNoOpPolicyPreserved`) so neither can
drift silently.

**Recommendation, for Mike:** stop auditing no-ops on `update_load()` too. It is a one-line guard,
it removes false entries only, and it would make all four paths identical. Not done here.

### 5.2 Activity ordering is ambiguous within one second

`store.list_activities()` sorts `ORDER BY created_at DESC`, and `created_at` has second precision.
Events written inside the same second tie, and their relative order is unspecified. This is
pre-existing — the same ambiguity M3 found in Route Risk — and out of C3's scope. Every assertion in
the C3 test module is membership-based rather than positional as a result. **A first-class event
sequence number belongs to the Spine Event-schema mission**, not here.

### 5.3 Live conflict store polluted during analysis — disclosed

My analysis probe scripts ran outside the test harness with no `PORTAL_DATA_DIR` set, so two refused
transitions wrote Conflict Notices into the working copy's live `portal/data/conflicts.json`
(400 entries → 402). The remaining 366 `invalid_status_transition` entries predate today and were
already disclosed in the M1 walkthrough report — they come from the suite run that happened before
the isolation fixture existed.

**Not cleaned up, deliberately.** Unresolved conflict notices are classified **protected** in the
proposed protected-state map, and purge is an Archive function under a retention policy that has not
been written. Deleting protected records to tidy my own mess would be a worse act than disclosing
it. `portal/data/` is gitignored, so nothing entered the repository. Mike may want these purged; that
is his call, under C4 or a retention decision.

---

## 6. Test results

**Full suite: `python -m pytest` — 2804 passed**, from a 2771 baseline. **33 new tests**, none
deleted or weakened.

`tests/test_status_change_audit.py` covers every property the mission required:

| Required | Covered by |
|---|---|
| 1. `update_load()` produces exactly one correct event | `TestUpdateLoadPath` — count, previous/new state, operation, timestamp format, non-status update writes nothing, actor not fabricated |
| 2. `add_milestone()` produces one equivalent event | `TestMilestonePath` — count, states, operation, actor recorded when supplied and absent when not, full ladder one-per-transition, chain without gaps |
| 3. Refusals produce no accepted event | `TestRefusalsAreNotAudited` — refused milestone, refused `update_load`, refusal after real changes |
| 4. Retained evidence must not imply the transition | `TestRetainedEvidenceDoesNotImplyTransition` — milestone kept, no audit event, status untouched, log never claims an unreached state |
| 5. Repeats/idempotent calls create no duplicates | `TestNoDuplicates` — repeated milestone, same-status siblings, double archive, no path chains into another |
| 6. Existing transition-gate tests green | `tests/test_milestone_transition_gate.py` — 28 tests, unchanged, passing |
| 7. Complete suite passes | 2804 passed |
| 8. Tests do not write live stores | Proven by mtime: `portal/data/conflicts.json` byte-identical before and after the refusal-heavy modules |

Plus `TestBoundariesHeld` — the store layer is still raw and unaudited, the transition matrix is
untouched, milestone recording is untouched, and `checkpoint` still produces no status event.

---

## 7. Boundaries — confirmation that nothing else changed

| Boundary | Held |
|---|---|
| Valid transition matrix | Untouched — asserted by `test_transition_matrix_untouched` |
| Milestone-recording behavior | Untouched — asserted by `test_milestone_recording_behavior_untouched` |
| M1 ruling: refused transition retains its milestone | Untouched — asserted by `TestRetainedEvidenceDoesNotImplyTransition` |
| No new state model | None created. No state name added, removed or renamed. |
| No Mission Layer implementation beyond the adjudication | None. No module, class or partition component created — one private helper in an existing service module. |
| Driver-First Doctrine | Not modified |
| Calendar behavior | Not touched |
| Capacity, scheduling, overnight, reset, replay ledger, Outlook | None implemented |
| Unrelated services | Not refactored — the diff is one file |
| Manager | Not touched |

**Files changed: 2.**

```
 M dispatch/services.py                    (helper + 4 call sites + 1 import)
?? tests/test_status_change_audit.py       (new, 33 tests)
```

No schema change, no migration, no template change, no route change, no dependency change.

## 8. Not started

C1, C2a, C2b, C4 and every other Build Matrix mission remain unstarted and unauthorized.
