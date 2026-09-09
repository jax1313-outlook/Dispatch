# Tab Walk — Dispatch

- Status: FINDINGS OPEN — code-side pass only. No runtime pass yet.
- Walked on: 2026-09-09 (implementation read, not exercised against a real load)
- Finding ID prefix: DISPATCH

## Scope

Nav entries: Dispatch, Operations, Calendar, Exceptions

Templates: dispatch.html, dispatch_detail.html, dispatch_decision.html, operations.html, calendar.html, exceptions.html, _sweep_panel.html

Routes:

- `GET /dispatch` — `portal/routes/pages.py:116`
- `GET /dispatch/<load_id>` — `portal/routes/pages.py:182`
- `GET /dispatch/<load_id>/rate-confirmation/print` — `portal/routes/pages.py:223`
- `GET /operations` — `portal/routes/pages.py:24`
- `GET /calendar` — `portal/routes/pages.py:323`
- `GET /exceptions` — `portal/routes/pages.py:658`

## What this tab is supposed to do

Show the committed work. Under R1 the record reaching this tab has already passed
Accept, so Dispatch is executing a mission, not evaluating an opportunity. The
constitution puts Dispatch downstream of commitment, executing deterministically
from that point forward.

## What it actually does

NOT YET WALKED. This section needs Mike at the screen with a real load. The
findings below come from reading the implementation and are unconfirmed against
a running load.

## The six questions

Read against `docs/architecture/DISPATCH_WORKER_CONSTITUTION_ARCHITECTURE.md`.
See `docs/tab-walk/LENS.md` for how to apply these and what is already settled.

**1. Which worker owns this function?**

Dispatch owns execution of a committed mission. That much is clear. What is not
clear is why this route also performs collection, scoring persistence and conflict
detection, which the constitution assigns to Intelligence. See DISPATCH-001.

**2. Is the tab displaying workflow, or defining workflow?**

Defining, in part. `GET /dispatch` writes. It creates sandbox entries, writes
scoring, runs conflict checks, and syncs engine status. A screen that is opened
changes stored state. See DISPATCH-001 and DISPATCH-002.

**3. Is worker responsibility incorrectly embedded in the screen?**

Yes. Collection and conflict detection sit in the page handler rather than behind
a defined condition. The trigger is a page view.

**4. What state transition does this screen represent?**

Post-Accept execution of one record. Under R1 this is the same record that was an
Opportunity Card, now carrying its encoded data forward under a new name. The tab
does not itself perform the Accept transition.

**5. What inputs, outputs, and handoffs are present?**

- Receives: engine loads from `dispatch.services.list_loads`, sandbox cards
  filtered to `source_type == "dispatch"`, lane templates, active drivers and
  equipment, stalled loads.
- Produces: rendered view; and as a side effect, new sandbox entries, scoring
  writes, conflict notices, engine-status writes.
- Hands off to: Conflict Notices, via `conflict.check_dispatch_card`.
- Handoff condition: none defined. It fires when the page is opened with no
  dispatch entries present, or with `?refresh`.

**6. Does the current implementation align with worker ownership?**

Partly. Execution belongs here. Collection, scoring persistence and conflict
detection do not, and they are the side effects of a GET.

## Findings

Every finding gets an ID. Never renumber. A closed finding keeps its number
so commits and tests can keep pointing at it.

### DISPATCH-001 — Opening the tab creates records and raises conflict notices

- Severity: wrong
- Status: open
- Lens: yes
- Evidence: `portal/routes/pages.py:135-151`
- Seen: when no dispatch sandbox entries exist, or `?refresh` is passed, the GET
  handler calls `helpers.load_dispatch_data()`, creates a sandbox entry per load,
  calls `sandbox.update_scoring`, and calls `conflict.check_dispatch_card`.
- Expected: a screen presents. Collection and conflict detection belong to a
  worker and should fire on a defined condition, not on a page view.
- Cause:
- Fix:
- Proven:

### DISPATCH-002 — Engine status is written to storage during a GET render

- Severity: wrong
- Status: open
- Lens: yes
- Evidence: `portal/routes/pages.py:152`, `portal/routes/pages.py:991-1005`
- Seen: `_sync_booked_entries` compares each card's stored `engine_status` to the
  engine's current status and calls `sandbox.update_engine_status` on drift,
  which writes to disk during the render.
- Expected: the screen reads. Reconciling card state to engine state is a handoff
  with an owner and a condition.
- Cause:
- Fix:
- Proven:

### DISPATCH-003 — Sort order can depend on when the page was opened

- Severity: broken
- Status: open
- Lens: no
- Evidence: `portal/models/sandbox.py:243`, `portal/routes/pages.py:1008-1018`
- Seen: `update_engine_status` sets `updated_at` to now. `_sync_booked_entries`
  runs immediately before the sort, and `_priority_key` uses `updated_at` as its
  final tiebreak. Two cards tied on active, score and priority can therefore swap
  position because one of them was touched by this render.
- Expected: R5 holds that sorting remains deterministic. Order should follow from
  the record and the policy profile alone, not from view time.
- Cause: not traced. The window is narrow. It requires a full tie on the three
  preceding key components and a drifted engine status on one of them.
- Fix:
- Proven:

### DISPATCH-004 — Two representations of one load are rendered side by side

- Severity: rough
- Status: open
- Lens: yes
- Evidence: `portal/routes/pages.py:125-131`, `portal/routes/pages.py:162-166`
- Seen: the template receives both `entries`, which are sandbox cards, and
  `engine_loads`, which are engine records. They are joined only by an optional
  `engine_load_id` on the card.
- Expected: R1 holds one record with one identity whose name changes at Accept.
  Two parallel stores linked by an optional field is worth reading against that.
- Cause:
- Fix:
- Proven:

### DISPATCH-005 — The financial dashboard renders on the Dispatch tab

- Severity: rough
- Status: open
- Lens: yes
- Evidence: `portal/routes/pages.py:130`
- Seen: `get_financial_dashboard()` is called here, and also on Home and Billing.
- Expected: question 1 has no answer yet for who owns money. Three screens
  present the same figures.
- Cause:
- Fix:
- Proven:

### DISPATCH-006 — Send Stall Alerts reports success while delivering nothing

- Severity: broken
- Status: open — CONFIRMED against source 2026-09-09 at Mike's request
- Lens: no
- Confirmed: `notified` is `len(check_stalled_loads(...))`. The endpoint calls
  `notify_stalled_loads`, which detects the stalled set, loops sending, and then
  returns the detected set unchanged. No send outcome reaches the count. A
  transport exception does not reduce it either, because `_notify_safe` catches
  every exception and prints to stderr. The number reports detection and is
  labelled delivery.
- Evidence: `portal/routes/dispatch_api.py:212-220`, `dispatch/services.py:1443-1451`,
  `cin_lite/email_delivery.py:159-164`, and the single artifact at
  `D:\Archive\CIN\Outbox\dispatch-stalled-SBX-DISPATCH-E2E-DEMO-001.eml`
- Seen: the endpoint returns `notified` set to the number of loads found
  stalled. It is not a count of alerts delivered. With no SMTP host configured,
  and none is configured on this machine, every message is written to a file
  instead of sent, and the transport's own result string saying so is discarded
  before anyone can see it. The button reports a positive number either way.
- Expected: a control that says alerts were sent should only say so when they
  were. At minimum the response should distinguish detected from delivered.
- Cause: `_notify_safe` runs each notification for its side effect and keeps no
  return value, by design, so a mail failure cannot fail a completed write. The
  cost is that the outcome is unavailable to the caller.
- Fix:
- Proven:

Full evidence and the three questions it raises are in
`docs/tab-walk/builder-notes/alerts-detection-generation-delivery-tracking.md`.

## Decisions made during this walk

None yet.

## Carried forward

- Conflict Notices receives handoffs from this tab with no defined condition.
  Tab 10 owns that surface and should confirm what arrives there and why.
- Who owns financial figures is unresolved and touches tabs 05 and 11.
