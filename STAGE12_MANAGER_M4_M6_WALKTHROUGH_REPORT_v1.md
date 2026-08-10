# STAGE12_MANAGER_M4_M6_WALKTHROUGH_REPORT_v1

## Manager -- Phase M5 (IFTA half only) and Phase M6 (Security Alert Monitor)

**Status:** Implemented and verified. Branch: `stage12-manager-foundation` (continues on top of the already-shipped M2+M3 build, commit `acb9d76`).

**Responds to:** "Approve Stage 12 build for phases M4-M6," followed by review and approval of `DISPATCH_STAGE12_MANAGER_M4_M6_BUILD_DESIGN_v1.md` ("Approve design").

---

## What Changed

1. **`dispatch/manager/security_monitor.py`** (new) — Phase M6. Reads `dispatch.security.store.list_security_events()` for a rolling 24-hour window, groups `LOGIN_FAILURE` events by identity (real `user_id` when known, `details.display_name` when not — deliberately never conflated) and `PERMISSION_DENIED` events by `(user_id, path)`, and emits one signal per group that reaches 3+ occurrences. `source_id` is stable per calendar day so an ongoing pattern doesn't re-materialize a duplicate Work Item within the same day, while a pattern continuing into a new day gets a fresh entry.
2. **`dispatch/manager/signals.py`** — extended with a sixth true signal source, `IFTA_EXCEPTION`: reads `dispatch.services.list_ifta_report_approvals()`, filters to `status == "draft"` (submitted, not yet sealed), and reads each one's exceptions via `list_ifta_exceptions(approval_id)`. Also now calls `security_monitor.detect_patterns()` and folds its output into the same signal stream.
3. **`dispatch/manager/classify.py`** — new classifiers: `IFTA_EXCEPTION` → `Review Needed` (advisory, matches `IFTAException`'s own "never blocks" doctrine); `security_pattern` → always `Conflict`, no graduated severity.
4. **`dispatch/manager/priority.py`** — both new source types assigned Tier 1 (safety/security/legal/compliance/authority) — an IFTA exception risks an inaccurate government filing; a security pattern is inherently a security matter regardless of which specific pattern fired.
5. **`dispatch/manager/staff_report.py`** — **unmodified.** The orchestrator was already source-type-agnostic; both new signal types flow through the existing classify → rank → dedup → materialize pipeline with zero changes to that file, exactly as the build design predicted.
6. **`tests/test_manager_foundation.py`** — 12 new tests.

**Zero new database tables. Zero Spine schema changes.** M6 makes exactly one call anywhere into `dispatch.security` — `list_security_events()` — and never writes to `users`, `pin_records`, `sessions`, or `security_events`.

## What Did Not Change

`portal/routes/manager.py`, `portal/templates/manager.html`, every existing route/page, `/settings`'s Stage 7 gating, and the three existing HMAC email-decision gates are all untouched.

## What Was Not Built (Per the Approved Design)

- **Phase M4 (Stage Gate Monitor)** — not attempted. It requires Manager to read Claude-3's stage/decision-log state, and no cross-repo read mechanism exists anywhere in this codebase. Flagged as an open question in the design, not silently built or silently skipped.
- **Phase M5's Archive half** — not attempted. `portal/models/archive.py` still has no Archive Review Queue (re-confirmed unchanged before this build began); that's a separate, not-yet-authorized Stage 6 build this build cannot manufacture a prerequisite for.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_manager_foundation.py` — **42 passed, 0 failed** (30 from M2+M3 + 12 new).
- Full suite: `python3 -m pytest -q` from the repo root — **2,444 tests, 0 failures, 0 errors** (2,432 from before this build + 12 new).
- Two test-writing bugs caught and fixed before this count, not implementation bugs: a naive `"login(" not in source` substring check tripped on this module's own docstring (which explains `auth.py`'s `login()` in prose) — narrowed to the actual qualified-call form `"auth.login("`, which no prose in either module happens to contain.

## Live Walkthrough

Run against a live Flask dev server (`python -m portal.app`, throwaway temp data directories) on `127.0.0.1:8093`.

```
GET /manager (empty state) -> 200

-- seed 3 LOGIN_FAILURE events, unknown identity "Suspicious User" --
GET /manager -> Summary: Conflict: 1, Review Needed: 0
  Card: "Repeated LOGIN_FAILURE (3x in 24h)" -- Conflict, Tier 1

-- seed a draft IFTA report approval with one exception --
GET /manager -> Summary: Conflict: 1, Review Needed: 1
  Card: "IFTA exception: fuel_no_miles" -- Review Needed, Tier 1
  (2 cards total, both correctly ranked ahead of any lower-tier signal)

-- seed 2 more LOGIN_FAILURE for the same identity (5 total today) --
GET /manager x2 -> still exactly 2 cards, no duplicate
DB check: work_items = 2 (security_pattern + ifta_exception), unchanged
  across repeated fetches -- dedup holds even as the underlying event
  count kept growing

-- seal the IFTA approval --
Fresh signals.collect_signals() call -> 0 IFTA_EXCEPTION signals
  (confirms sealed quarters are correctly excluded from new detection)
GET /manager -> still 2 cards; the already-materialized IFTA exception
  card remains visible (the flagged, accepted limitation from the
  build design -- this build does not retract cards for signals that
  later become inactive; confirmed live, matching the design's stated
  behavior exactly, not a surprise)

-- unaffected surfaces --
GET /home            -> 200
GET /settings (no session) -> 302 Location: /login?next=/settings
```

The dev server was stopped and its throwaway data directories removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **M4 remains unresolved.** The cross-repo read question (§1 of the build design) needs a Mike decision before it can be scoped at all.
- **M5's Archive half remains blocked** on the not-yet-authorized Archive Review Queue build (Stage 6).
- **The security pattern threshold (3 events / 24 hours) is a documented, tunable default**, not doctrine — same status as every other classification threshold in this build.
- **A sealed IFTA exception's card lingers** rather than being retracted or marked resolved — acceptable given IFTA exceptions are explicitly advisory/historical regardless of seal status, but worth knowing before relying on `/manager` as a complete "what's currently true" view rather than "what's been flagged and not yet acted on."

---

*End of STAGE12_MANAGER_M4_M6_WALKTHROUGH_REPORT_v1.*
