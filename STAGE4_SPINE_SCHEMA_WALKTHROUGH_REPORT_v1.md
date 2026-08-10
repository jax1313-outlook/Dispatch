# STAGE4_SPINE_SCHEMA_WALKTHROUGH_REPORT_v1

## Dispatch Spine Core Schemas and State Transition Guard

**Status:** Implemented and verified. Branch: `stage4-spine-schemas` (based on `stage3-blueprint-alignment`, which is based on `stage2-documentation-import`).

**Responds to:** Mike's approval ("Approve Stage 4") of the Migration Plan's Stage 4 (Data Engine / Spine Reconciliation), following his answers to Stage 4's two open questions ("Same file, coexist during transition") and his review of `DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md`, which this implementation follows.

---

## What Changed

1. **`dispatch/spine/models.py`** (new) — six dataclasses mirroring `dispatch/models.py`'s existing style (`_gen_id`/`_utc_now`/`_validate_choice` reused, not reinvented): `WorkItem`, `Event`, `PortalCard`, `ApprovalEvent`, `ConflictEvent`, `AuditEvent`. Field names and types follow `docs/DISPATCH_SPINE_SPECIFICATION_v1.md` Sections 5–14.
2. **`dispatch/spine/state.py`** (new) — `STATE_LIST` (25 states) and `ALLOWED_TRANSITIONS` (the full transition table) from the Spine Spec, plus `transition()`, the single function that computes a validated state change and its `Event`. A module-load-time assertion confirms `ALLOWED_TRANSITIONS` covers every state and every named destination is real, so a typo fails loudly instead of silently misbehaving.
3. **`dispatch/spine/db.py`** (new) — `init_spine_schema(conn)`, idempotent `CREATE TABLE IF NOT EXISTS` DDL for the six tables, in dependency order (`work_items` → `events` → `portal_cards` → `audit_events` → `approval_events` → `conflict_events`).
4. **`dispatch/spine/store.py`** (new) — CRUD functions mirroring `dispatch/store.py`'s style. `apply_transition()` is the only function that may update `work_items.current_state`; it wraps `transition()` and the resulting `Event` insert in one connection.
5. **`dispatch/db.py`** — one addition to `_init_db()`: a deferred import and call to `dispatch.spine.db.init_spine_schema(conn)`, so Spine tables are created in the same file, same connection, same migration pass as the 27 existing tables. No existing schema, table, or migration touched.
6. **`tests/test_spine.py`** (new) — 23 tests: schema creation/idempotency, round-trip serialization for all six schemas, the full `is_allowed()` transition matrix, `apply_transition()` happy-path and rejection cases, the interim-identity-gap assertion, and a structural guard confirming `current_state` is written in exactly one place.

## What Did Not Change

`LoadActivity`/`activities` — untouched, continues logging Load-scoped comments/status-changes exactly as before, per Mike's explicit "coexist" answer to Open Question 2. No existing table, model, service function, route, or template was modified. No Portal UI wired to any Spine table yet — that begins at Stage 5. No `users`/`sessions` table — that's Stage 7; `approval_events.session_id`/`user_id`/`role` are deliberately nullable and unauthenticated until then.

## Deviations From the Literal Approved Design (Flagged, Not Silent)

Per this codebase's own established convention of naming real scope decisions rather than absorbing them quietly:

1. **ID format.** The approved design document proposed plain UUIDs, matching the Spine Spec's own JSON examples literally. During implementation, every one of the 15+ existing entity types in `dispatch/models.py` was confirmed to use the `_gen_id(prefix)` convention (`PREFIX-YYYYMMDD-hex8`) with zero exceptions. Reuse-before-rebuild favored matching that universal convention over introducing the one plain-UUID scheme in the codebase. Easy to revert to plain UUIDs if Mike prefers the Spec's literal format — it's a one-line change per model's `__post_init__`.
2. **Transition table completeness.** The Spine Spec's §7 prose only defines outgoing transitions for states that have any; the five `ROUTED_TO_*` states are named only as destinations. The implementation adds explicit empty-list entries for all five, so every state in `STATE_LIST` has a defined (possibly empty) entry — consistent with "no routing rule may create hidden decisions." This is an interpretive completion of the spec, not a change to any transition it did define.

## Automated Test Results

Full suite: `python -m pytest -q` from the repo root — **all tests pass, 2,352 tests, 0 failures, 0 errors** (includes the 23 new tests in `tests/test_spine.py` plus the full pre-existing suite, confirming zero regression).

## Live Walkthrough

No Flask route exists yet to exercise over HTTP (Portal wiring is Stage 5), so this walkthrough exercises `dispatch.spine.store` directly against a real, throwaway SQLite file — the same rigor as prior phases' dev-server walkthroughs, adapted to what this stage actually built.

```
1. work_item created: WI-20260810-0A575F96 CREATED
   -> VALIDATION_PENDING
   -> VALIDATED
   -> SCORING_PENDING
   -> SCORED
   -> PORTAL_CARD_PENDING
   -> PORTAL_CARD_CREATED
   -> WAITING_FOR_MIKE

2. portal_card created: CARD-20260810-29C6364B level 3
   required_closing: This is a recommendation only. No action is authorized. Mike decides.

3. invalid transition correctly rejected: InvalidTransitionError -
   'WAITING_FOR_MIKE' -> 'SCORED' is not an allowed transition

4. approval_event created: APV-20260810-6878349F
   linked audit_id: AUD-20260810-38BE728A   user_id: None

5. conflict_event created: CNF-20260810-D5841CA1

6. events logged: 8, audit_events logged: 1

7. all tables in dispatch.db: ['activities', 'approval_events', 'audit_events',
   'broker_contacts', 'compliance_documents', 'conflict_events',
   'detention_events', 'driver_pay', 'drivers', 'equipment', 'events',
   'evidence', 'exceptions', 'expenses', 'ifta_exceptions',
   'ifta_fuel_evidence', 'ifta_fuel_purchases', 'ifta_report_approvals',
   'ifta_trip_legs', 'lane_templates', 'loads', 'maintenance_schedules',
   'milestones', 'pod_packages', 'portal_cards', 'rate_confirmations',
   'retention', 'settlements', 'visibility', 'work_items']

8. temp db removed, no repository files touched.
```

All eight scenarios behaved exactly as designed: a real Work Item walked through seven real state transitions with the required Event logged at each step; an invalid transition (`WAITING_FOR_MIKE → SCORED`) was correctly rejected without moving state or logging a spurious event (asserted directly in `test_apply_transition_rejects_invalid_move`); a Portal Card rendered the fixed Constitution §17 closing sentence automatically; an Approval Event correctly created its linked Audit Event in the same transaction and recorded `user_id: None`, demonstrating the interim identity gap is real and visible, not silently defaulted to something that looks authenticated; and all six new tables sit alongside all 24 pre-existing tables in one file, confirming Open Question 1's "same file" decision.

## Risk Notes Carried Forward

- **Interim identity gap is real until Stage 7.** Any code that writes an `approval_events` row before Stage 7 lands must not present `user_id: None` as if it were an authenticated approval — this schema makes the gap visible in data, it does not close it. `test_approval_event_interim_identity_gap_is_nullable` exists specifically so this can't silently change (tighten or loosen) without a test update forcing a conscious decision.
- **`events` and `activities` coexistence is a deliberate, temporary state**, not a final architecture. Per Mike's answer to Open Question 2, whether/how they consolidate is an explicitly later decision (candidate: Stage 11, when Sandbox generalizes into the Work Item shape) — not assumed or pre-decided here.
- **No Portal surface uses any of this yet.** These tables exist and are tested but are not reachable through any route or template — Stage 5 is where that begins. Nothing in this stage changes observable application behavior.

---

*End of STAGE4_SPINE_SCHEMA_WALKTHROUGH_REPORT_v1.*
