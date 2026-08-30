# M1_MISSION_TRANSITION_GATE_WALKTHROUGH_REPORT_v1

## Mission State Transition Gate Closure

**Status:** Implemented and verified. Branch: `claude/dispatch-repo-context-reconcile-7mblbb`.

**Mission:** M1 of `DISPATCH_BUILD_MATRIX_v1` (Level 1 — defect).

**Closes:** The repository's own long-standing open item, named in
`tests/test_status_transition_gate.py`'s module docstring as *"a separate, not-yet-attempted item
referred to elsewhere as finding #5 / A1"*, and recorded as B-18 in
`DISPATCH_REPO_RECONCILIATION_PLAN_v1`.

---

## The defect

`add_milestone()` computed the derived status from `_MILESTONE_TO_STATUS` and wrote it straight
through `store.update_load()` (`dispatch/services.py:393-396`). `store.update_load()` performs no
validation at all (`dispatch/store.py:151-169`). A load could therefore move between **any** two
statuses in one call — `created` → `delivered`, skipping five states — while `archive_load()` was
the only path that ever called `validate_status_transition()`.

The transition table was not aspirational; it existed, was correct, and was already enforced on one
path. It simply was not enforced on the path most used to advance a load.

## What changed

1. **`dispatch/services.py`**
   - `add_milestone()` now gates its status cascade on `validate_status_transition()` — the same
     table `archive_load()` already used. No status was added, removed, or renamed; the table is
     untouched.
   - New `_raise_transition_refusal_card()` — surfaces a refusal as a Conflict Notice. The import
     of `portal.models.conflict` is **soft**, matching the existing pattern in
     `get_publisher_status()`: the load engine must keep working when the portal package is not
     importable. If the card cannot be raised, the refusal still goes to stderr — a missing card
     surface must not become a lost refusal.
   - The `delivered` notification now fires only when the load actually reached `delivered`.
     Announcing a delivery for a load whose transition was just refused would report a state the
     load is not in, and this notification is one step from being broker-facing.
2. **`portal/models/conflict.py`** — one new type, `invalid_status_transition`, appended to
   `CONFLICT_TYPES`.
3. **`portal/routes/dispatch_api.py`** — `POST /loads/<id>/milestones` returns **409** with the
   reason when the transition was refused, instead of `201 ok`. A driver at a dock must not read
   "ok" and assume the load advanced.
4. **`tests/conftest.py`** — see "Incidental fix" below.

## The design decision, stated as an assumption (BM-08)

> **The milestone is always recorded. What is refused is the transition.**

A milestone is a record that something was *reported to have happened*; discarding it would lose
evidence, which is the opposite of what a gate is for. The load's status is left exactly as it was,
a card is raised, and the returned dict carries a non-persisted `status_transition_refused` key.

This was a genuine choice and the alternative was considered: refusing the whole operation. It was
rejected on three grounds.

| | Refuse everything | **Record, refuse only the transition** (chosen) |
|---|---|---|
| Evidence | A reported event is discarded | Preserved |
| Blast radius | `generate_pod()` on a `completed`/`archived` load would start raising, breaking an unrelated operation | POD generation unaffected |
| Test fallout | ~100 call sites at risk | 26 tests, all genuine skips |

**This assumption requires Mike's confirmation.** If the intent is that an out-of-order milestone
should be rejected outright, that is a different behavior and a different mission.

Second assumption: refusals are raised at severity `warning`, not `critical`. A refused transition
needs human attention but is not an emergency. Also open to correction.

## Enumerated behavior change (BM-09)

The complete list, computed from the transition table rather than inferred from test failures:
**90 of 121 (status × milestone) pairs are now refused; 31 are accepted** (11 advance the status,
20 are same-status no-ops). `checkpoint` maps to no status and is never gated.

| Load status | Milestones still accepted |
|---|---|
| `created` | dispatched |
| `dispatched` | dispatched (no-op), en_route_pickup |
| `en_route_pickup` | en_route_pickup (no-op), arrived_pickup |
| `at_pickup` | arrived_pickup (no-op), loaded |
| `picked_up` | loaded (no-op), departed_pickup, in_transit |
| `in_transit` | departed_pickup / in_transit (no-op), arrived_delivery |
| `at_delivery` | arrived_delivery (no-op), delivered, pod_received |
| `delivered` | delivered / pod_received (no-op), completed |
| `completed` | completed (no-op) |
| `archived`, `cancelled` | none |

The count is pinned by `test_refused_pair_count_is_stable`, so a later change to the table or the
milestone map cannot silently move it.

**What this refuses that used to work:** any ladder skip. The most common in practice was
`dispatched` → `arrived_pickup` (skipping `en_route_pickup`), which the repository's own
`delivered_load` fixture relied on.

## Regression surface — 26 tests, every one a real skip

All 26 were **rewritten to walk the ladder, never deleted or weakened**:

| File | Change |
|---|---|
| `tests/test_dispatch.py` | `delivered_load` fixture and two API/notification ladders gain `en_route_pickup` |
| `tests/test_status_transition_gate.py` | `_deliver()` / `_complete()` helpers walk the real ladder; module docstring updated (it previously stated the cascade was untouched) |
| `tests/test_booking.py` | lifecycle ladder |
| `tests/test_financial_notifications.py`, `tests/test_financials.py` | archive ladders |
| `tests/test_portal.py` | order-sensitive `CONFLICT_TYPES` assertion — the new type was **appended** rather than inserted, so this assertion stays a meaningful check rather than being rewritten around it |

## Incidental fix, disclosed

The suite was writing into the **real** `portal/data/` directory. `tests/conftest.py::_scrub_env`
deletes `PORTAL_DATA_DIR`, so `get_data_dir()` fell back to the live path; `portal/data/conflicts.json`
had accumulated 400 entries, including two types (`data_mismatch`, `missing_data`) that are not in
`CONFLICT_TYPES` at all. This predates M1 — any test touching `check_booking_conflicts` already did
it — but M1 makes refusals a common path and would have made it much worse.

One line added to the existing `tmp_archive` fixture, whose stated purpose is already "redirect
every archive + email + pending write into a per-test tmp directory". **Zero tests changed
behavior.** The real `portal/data/` is now untouched by a full run.

## Second-order consequence, disclosed

`generate_pod()` records a `pod_received` milestone, which maps to status `delivered`. POD-eligible
statuses are `delivered`, `completed`, `archived` (`dispatch/services.py:629`). So:

| Load status when POD generated | Before M1 | After M1 |
|---|---|---|
| `delivered` | no-op (same status) | unchanged — no card |
| `completed` | **status silently regressed to `delivered`** | status stays `completed`; one card raised |
| `archived` | **status silently regressed to `delivered`** | status stays `archived`; one card raised |

Verified live: POD generation still succeeds, the milestone is still recorded, and the status no
longer moves backwards. The backwards regression was a real bug this gate now prevents.

The card on a completed/archived load is the debatable part — a POD arriving after completion may be
routine rather than anomalous. It is left as a card because suppressing it would mean the gate
choosing which refusals matter, which is discretion a deterministic component may not hold. **If Mike
judges this noise, the fix belongs in `generate_pod()`'s eligibility rule, not in the gate.**

## Known defect observed, deliberately not fixed

The Conflict Notice scope key is `f"LOAD-{load_id}"`, and load ids already start with `LOAD-`, so
notices are scoped to `LOAD-LOAD-20260821-...`. This is **the existing repository convention** —
`dispatch/services.py:1660` (`get_publisher_status`) and `portal/routes/dispatch_api.py:593`
(`end_load`) both produce it, and publisher actions for freight loads are already keyed this way.
Diverging would break correlation between a refusal card and the publisher action for the same
load. Recorded as a cosmetic defect for a future mission; not changed here.

## Automated test results

Full suite: `python -m pytest` — **2771 passed** (baseline before this branch: 2705).
28 new tests in `tests/test_milestone_transition_gate.py`: legal ladder end to end, every ladder
step lands on its status, the closed bypass, backwards transitions, milestone still persisted on
refusal, visibility showing the real status rather than the refused target, `checkpoint` ungated
from every status, same-status siblings not treated as refusals, the card raised and de-duplicated,
a card-surface failure not losing the milestone, notification suppressed on refusal and still sent
on acceptance, the API's 409/201/404 cases, and an exhaustive matrix asserted against
`validate_status_transition()` rather than a frozen list.

One test deliberately asserts that `store.update_load()` is **still** unvalidated — it is the layer
the gate is built on, not a second gate — so nobody reads M1 as more coverage than it is.

## Live walkthrough

Real Flask server on `127.0.0.1:8109`, throwaway data roots, never production data.

```
POST /loads                                     -> LOAD-20260821-A7142C75 (status: created)

POST /loads/<id>/milestones {"delivered"}       -> HTTP 409
   status  : refused
   error   : Milestone recorded, but the load stays in 'created':
             Invalid status transition: created -> delivered.
             Allowed from created: cancelled, dispatched
   load status after : created          <- unchanged
   timeline          : ['delivered']    <- milestone still recorded

conflicts.json ->
   invalid_status_transition | warning | LOAD-LOAD-20260821-A7142C75
   "Refused status transition for load ...: created -> delivered."
   -> "Record the intervening milestone(s) in order, or correct the load's
       status, before recording a 'delivered' event."

Full legal ladder:
   dispatched        HTTP 201 -> dispatched
   en_route_pickup   HTTP 201 -> en_route_pickup
   arrived_pickup    HTTP 201 -> at_pickup
   loaded            HTTP 201 -> picked_up
   departed_pickup   HTTP 201 -> in_transit
   arrived_delivery  HTTP 201 -> at_delivery
   delivered         HTTP 201 -> delivered

Outbox: exactly ONE mail -- dispatch-delivered-<id>.eml
   (the refused delivery announced nothing; the accepted one did)

POST /loads/<id>/milestones {"checkpoint"}      -> HTTP 201, status stays delivered
```

## Boundaries observed

No layer was created or named — this enforces a table that already existed under names the
repository already uses, so it does not depend on the open Level 0 adjudication (D-1 / D-2).
Manager untouched. No calendar. Portal remains a display surface; the Conflict Notice store is the
raising element's record, and the Driver Portal still only reads. No judgment was added: the gate
evaluates, refuses, and raises — it never chooses between two legitimate outcomes.
