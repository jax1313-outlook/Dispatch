# DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1

**Document Type:** Evidence inventory (read-only)
**Program:** Dispatch
**Mission:** M0 of `DISPATCH_BUILD_MATRIX_v1`
**Status:** Complete for the repository at the commit this document lands on.
**Authority:** Mike Zachary remains final authority.

---

## 1. What this is, and what it deliberately is not

Every place the repository causes a side effect, with its call site, its subject, and whether it is
guarded against running twice. A side effect here means: mail leaves the process, a record is
created because a *different* record changed, or a status cascades.

**This document proposes nothing.** It does not say which triggers should exist, does not name a
layer, does not design a registry, and does not recommend any change. It is the evidence base a
future trigger registry would be built from, and the evidence base the replay-safety work (M5)
needs before it can claim completeness.

Per BM-01, building a registry is architectural work requiring its own review. This is the sweep
that would precede it.

**Method.** Symbol sweeps across `dispatch/`, `portal/`, `cin_lite/`, `route_risk/` and `sync/` for
`notify_*`, `_notify_safe`, `email_delivery.send`, `deliver_*`, `_trigger_*`, `create_action`,
`create_notice`, `create_packet`, `archive_from_sandbox`, `promote_to_candidate`, and every
`store.update_load(..., status=...)` write. Test files excluded.

---

## 2. Headline counts

| | Count |
|---|---|
| Distinct side-effect call sites | 32 |
| Of those, mail leaving the process | 17 |
| Guarded — a repeat cannot produce a duplicate | 14 (protected by 8 distinct mechanisms) |
| Unguarded | 15 |
| Listed from the call site, not separately exercised in this pass | 3 |
| Time-based triggers (a clock causing anything) | **0** |
| Background workers, schedulers, daemons, queues | **0** |

Every side effect in this repository is initiated by an inbound HTTP request or a manual CLI
invocation. Nothing fires on a clock.

---

## 3. Trigger type A — state change causes mail

All of these run through `dispatch/services.py::_notify_safe()` (`dispatch/services.py:43`), which
deliberately swallows delivery failures so a transport problem cannot break the write that preceded
it. Each fires strictly *after* its database write.

| # | Fires on | Call site | Enclosing function | Recipient | Guarded? |
|---|---|---|---|---|---|
| A1 | Driver + equipment both assigned to a `created` load | `dispatch/services.py:302` | `_try_auto_dispatch()` (def `:278`) | Reviewer | **Yes** — precondition `status != "created"` returns early (`:280`), so a second assignment cannot re-fire. |
| A2 | Milestone `delivered` recorded | `dispatch/services.py:410` | `add_milestone()` (def `:369`) | Reviewer | **No** — `add_milestone()` has no uniqueness constraint; recording `delivered` twice sends twice. |
| A3 | Exception opened at severity high/critical | `dispatch/services.py:577` | `open_exception()` (def `:543`) | Reviewer | **No** — two identical exceptions send twice. |
| A4 | POD package generated | `dispatch/services.py:671` | `generate_pod()` (def `:632`) | Reviewer | **No** |
| A5 | Load archived | `dispatch/services.py:768` | `archive_load()` (def `:721`) | Reviewer | **Yes** — existing retention record raises before the notify (`:726-728`). |
| A6 | Settlement created (invoice) | `dispatch/services.py:1017` | `create_settlement()` (def `:993`) | Reviewer | **No** |
| A7 | Payment recorded | `dispatch/services.py:1048` | `record_payment()` (def `:1025`) | Reviewer | **No** |
| A8 | Settlement passes its due date | `dispatch/services.py:1184` | `check_overdue_settlements()` (def `:1164`) | Reviewer | **Yes** — selects `payment_status="invoiced"` and writes `"overdue"`, so the second scan does not select it again. |
| A9 | Settlement disputed | `dispatch/services.py:1209` | `dispute_settlement()` (def `:1190`) | Reviewer | **No** |
| A10 | Settlement written off | `dispatch/services.py:1232` | `write_off_settlement()` (def `:1213`) | Reviewer | **No** |
| A11 | Load exceeds its stall threshold | `dispatch/services.py:1288` | `notify_stalled_loads()` (def `:1281`) | Reviewer | **No** — re-sends for every currently-stalled load on every call. Only caller is `POST /api/dispatch/loads/stalled/notify` (`portal/routes/dispatch_api.py:214`). |

**Note on A11 and the outbox.** When SMTP is unconfigured, `_send_or_write()` writes to
`Archive/Outbox/<fallback_id>.eml` (`cin_lite/email_delivery.py:82-98`). The stall fallback id is
`dispatch-stalled-<load_id>` (`dispatch/notifications.py:504`) — deterministic, so a repeat
*overwrites the same file*. In an unconfigured environment a duplicate send leaves exactly one
file and is invisible. With SMTP configured it is a real second email. Any test asserting replay
safety must assert on a record, never on the outbox.

---

## 4. Trigger type B — human action causes mail

| # | Fires on | Call site | Guarded? |
|---|---|---|---|
| B1 | Contract processed through the pipeline → checkpoint email with HMAC action buttons | `cin_lite/pipeline.py:76` (`deliver_checkpoint`) | **No** — `process_contracts()` (`:20`) re-acquires and re-processes every source file on every invocation with no already-processed check. |
| B2 | Reviewer clicks a decision button → confirmation email | `cin_lite/pipeline.py:125` (`deliver_decision`) | **Yes** — `pending.complete()` (`cin_lite/pending.py:60`) deletes the pending file; a second click raises `No pending decision` (`cin_lite/pipeline.py:105-107`). |
| B3 | Decision action is a proposal trigger → proposal email | `cin_lite/workflows/proposal.py:158` | Inherits B2's guard (only reachable through `resolve_decision`). |
| B4 | Completion email package submitted → broker + customer mail | `dispatch/email_helper.py:262` | **Yes** — status `SUBMITTED` short-circuits before any send (`dispatch/email_helper.py:245-246`). |
| B5 | Portal email package submitted → broker + customer mail | `portal/models/email_helper.py:298` | **Yes** — same short-circuit as B4, and self-documented in the source: *"idempotent -- re-submitting is a no-op, not a re-send"* (`:280`). |
| B6 | IFTA quarterly approval requested → approval email with HMAC link | `dispatch/services.py:2681` | **No** — requesting approval twice creates a second approval record and sends a second email. The *approve* side is guarded: `approve_ifta_quarter()` (def `:2695`) is a documented no-op success on an already-sealed approval. |

Mail transport for every row above is `cin_lite/email_delivery.py`. There is exactly one transport
and it is stdlib SMTP. `dispatch/customer_notifications.py` is a customer/broker-facing boundary
that exists and is **deliberately not wired into any lifecycle** (`tests/test_deployment_boundaries.py:1-16`).

---

## 5. Trigger type C — record change causes another record

| # | Fires on | Call site | Creates | Guarded? |
|---|---|---|---|---|
| C1 | Sandbox action `BOOK` | `portal/routes/api.py:56` | Engine load | **Yes** — `engine_load_id` present → HTTP 409 (`:47-49`). |
| C2 | Sandbox action `BOOK`, same request | `portal/routes/api.py:67` | Rate confirmation (`_auto_rate_confirm`, def `:565`) | Inherits C1's guard. |
| C3 | Sandbox action `BOOK`, same request | `portal/models/conflict.py:178` via `:52` | Conflict notices (overlap, turnaround) | **Yes** — `create_notice()` dedupes unresolved notices on type + sandbox + explanation (`:69-77`). |
| C4 | Sandbox action `PURSUE` | `portal/routes/api.py:81` | Publisher action | **No** — `create_action()` appends unconditionally (`portal/models/publisher.py:95`). |
| C5 | Sandbox action `PASS` | `portal/routes/api.py:90` | Archive record | **No** — `archive_from_sandbox()` (`portal/models/archive.py:111`) calls `create_record()` with no existence check. |
| C6 | Library candidate approved with Intelligence provenance | `portal/models/library.py:161` → `_trigger_publisher_on_approval()` (def `:166`) → `:181` | Publisher action | **No** |
| C7 | Publisher action reaches a GovCon draft type | `portal/models/publisher.py:150` → `_trigger_govcon_draft()` (def `:161`) | Proposal draft reference | Bounded by the action's own status ladder. |
| C8 | Intelligence record promoted to a Library candidate | `portal/routes/api.py:463` | Library candidate | Not verified in this sweep. |
| C9 | End Load | `portal/routes/dispatch_api.py:567` | Completion packet | **Yes** — existing packet returns `already_ended` (`:557-559`), and `create_packet()` itself returns the existing packet (`portal/models/completion_packet.py:64-66`). |
| C10 | End Load, same request | `portal/routes/dispatch_api.py:573` | Publisher action | Inherits C9's guard. |
| C11 | IFTA approval requested | `dispatch/services.py:2670` | IFTA exception records, one per detector finding | **No** — see B6. |

---

## 6. Trigger type D — status cascades

| # | Fires on | Call site | Effect | Guarded? |
|---|---|---|---|---|
| D1 | Any milestone whose type maps to a status | `dispatch/services.py:393-396` | `store.update_load(status=...)` | **No.** `store.update_load()` performs no transition validation (`dispatch/store.py:151-169`), so this path can move a load between any two statuses, including illegal jumps. |
| D2 | Any milestone | `dispatch/services.py:398-407` | Visibility record upserted (last + next expected milestone, exception flag) | Idempotent by upsert, but reflects whatever D1 wrote. |
| D3 | Driver + equipment assignment | `dispatch/services.py:284` | `store.update_load(status="dispatched")` | Guarded by the `status != "created"` precondition at `:280`. The write itself is unvalidated; the precondition makes an illegal transition unreachable. |
| D4 | `archive_load()` | `dispatch/services.py:730` | Status → `archived` | **Yes** — this is the one path that calls `validate_status_transition()`. |

D1 is the defect M1 addresses. D3 is unvalidated but unreachable-illegal; it is recorded here for
completeness and is deliberately out of M1's scope (minimum diff).

---

## 7. Sweeps that exist but nothing calls on a clock

| Function | Location | Current caller |
|---|---|---|
| `run_hold_sweep()` — deletes sandbox entries past their 3-hour HOLD clock | `portal/models/sandbox.py:277` | **None outside tests.** |
| `check_stalled_loads()` | `dispatch/services.py:1248` | Four read-only surfaces (`portal/routes/pages.py:56`, `:158`, `portal/models/operations_feed.py:180`, `portal/routes/dispatch_api.py:208`) — display only, no side effect. |
| `notify_stalled_loads()` | `dispatch/services.py:1281` | One POST route (`portal/routes/dispatch_api.py:214`). |
| `check_overdue_settlements()` | `dispatch/services.py:1164` | Route-driven only. |
| `SyncEngine.run()` | `sync/engine.py:32` | `run_sync.py` / `run_sync.bat`, manual. |
| `process_contracts()` | `cin_lite/pipeline.py:20` | `cin_lite/run.py` CLI and a portal route. |

---

## 8. Existing replay guards, collected

The repository has converged on one pattern from several directions independently: **a side effect
is guarded by the presence of the record it produces.**

| Guard | Mechanism | Location |
|---|---|---|
| Load cannot be booked twice | `engine_load_id` present → 409 | `portal/routes/api.py:47-49` |
| Load cannot be archived twice | Existing retention record raises | `dispatch/services.py:726-728` |
| Completion packet cannot be assembled twice | Existing packet returned unchanged | `portal/models/completion_packet.py:64-66` |
| Load cannot be "ended" twice | `already_ended` response | `portal/routes/dispatch_api.py:557-559` |
| Email package cannot be sent twice | Status `SUBMITTED` short-circuits | `dispatch/email_helper.py:245-246` |
| Contract decision cannot be resolved twice | Pending file deleted on completion | `cin_lite/pending.py:60` |
| Conflict notice does not duplicate | Deduped on type + sandbox + explanation while unresolved | `portal/models/conflict.py:69-77` |
| IFTA quarter cannot be sealed twice | No-op success on an already-sealed approval | `dispatch/services.py:2695` |

Eight distinct mechanisms protect fourteen call sites. Fifteen call sites are unguarded: **A2, A3,
A4, A6, A7, A9, A10, A11, B1, B6, C4, C5, C6, C11, D1**. Three (C7, C8, and the concurrency
behavior noted below) are listed from their call sites and were not separately exercised.

---

## 9. Assumptions recorded (BM-08)

1. **"Side effect" is scoped to mail, cross-record creation, and status cascade.** Ordinary writes
   to a record's own store are not counted. A different definition would produce a different count.
2. **The sweep is symbol-based.** A side effect reached through a name not in the searched set, or
   through dynamic dispatch, would be missed. No such case was found, but absence of evidence is
   recorded as such rather than claimed as proof.
3. **C7 and C8 are listed from their call sites and were not separately exercised** in this pass.
   Their guard status is marked accordingly rather than asserted. B5 was verified directly.
4. **"Guarded" means a repeat cannot produce a duplicate side effect**, not that the guard is
   concurrency-safe. None of the eight guards is transactional across a check and its write; two
   simultaneous requests could pass the same check. Concurrency is out of scope here.

## 10. What this document does not conclude

It does not recommend closing any gap, does not propose a ledger design, and does not say which of
the nineteen unguarded sites matter. Those are M5, which is held under BM-01 pending review.
