# STAGE12_MANAGER_M7_POLICY_HOOK_WALKTHROUGH_REPORT_v1

## Manager -- Policy Routing Hook Candidate (Auto-log counts only, not a policy engine)

**Status:** Implemented and verified. Branch: `stage12-manager-m7-policy-hook` (based on `stage12-manager-archive-wiring`).

**Responds to:** Mike's "Approve Stage 12 build for M7," followed by review and approval of `DISPATCH_STAGE12_MANAGER_M7_POLICY_HOOK_DESIGN_v1.md` ("Approve design").

---

## What This Is, Restated

Not a policy engine. Not "GX." A read-only endpoint exposing only the count of Auto-log-tier (card_level 0: `Routine`, `Noise`) signals from Manager's existing Staff Report — the one classification tier `MANAGER.md` itself names as the only one a future automated system could ever safely touch. No individual record data. No write, approval, or action capability anywhere in the new code. Nothing in this codebase consumes the new endpoint; it defines an interface shape, not a working system.

## What Changed

1. **`dispatch/manager/policy_candidates.py`** (new) — one function, `auto_log_summary()`. Calls the existing, unmodified `staff_report.generate_staff_report()` and filters its already-computed `counts` dict down to `Routine`/`Noise` only.
2. **`portal/routes/manager.py`** — new `GET /api/manager/policy-candidates`, returning `auto_log_summary()` as JSON. No `methods=` argument — GET-only by Flask default, same convention as `/manager` itself.
3. **`tests/test_manager_foundation.py`** — 8 new tests.

## What Did Not Change

`staff_report.py` is untouched — the ninth consecutive extension of this pipeline to require zero orchestrator changes. `/manager`'s own page, `/settings`, `/home`, and every other route behave exactly as before.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_manager_foundation.py` — **66 passed, 0 failed** (58 from the prior four build passes + 8 new).
- Full suite: `python3 -m pytest -q` from the repo root — **2,489 tests, 0 failures, 0 errors** (2,481 from before this build + 8 new).
- Structural guard confirms `policy_candidates.py` contains no call to `create_approval_event`, `apply_transition`, `mark_reviewed`, `create_user_with_pin`, `book`, `approve_ifta_quarter`, or `deliver_decision` — the most important guard in this build, given what the phase touches.

## Live Walkthrough

Run against a live Flask dev server on `127.0.0.1:8097`.

```
GET /api/manager/policy-candidates (empty state) -> 200
  {"auto_log_counts": {}, "note": "...not a working policy engine."}

-- seeded one Noise-tier (info severity, no human decision required) and
   one Conflict-tier (critical severity) Conflict Notice --

GET /api/manager/policy-candidates -> 200
  {"auto_log_counts": {"Noise": 1}, "note": "..."}
  -- Conflict correctly absent

GET /manager -> Summary shows BOTH "Conflict: 1" and "Noise: 1"
  -- confirms the new endpoint is purely additive; /manager's own
     view is unaffected and still shows everything it always has

-- no individual record data --
Response contains no "SBX-WALK-NOISE" or "SBX-WALK-CONFLICT" (the
  seeded notices' sandbox_ids) anywhere -- counts only, confirmed

-- method + auth boundary --
POST /api/manager/policy-candidates -> 405 (GET-only, Flask default)
GET  /home            -> 200 (unaffected)
GET  /settings (no session) -> 302 Location: /login?next=/settings
```

The dev server was stopped and its throwaway data directories removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **This endpoint has no consumer.** It exists solely as a defined interface shape. If Mike ever wants an actual system built against it, that is explicitly named in the design as a separate future mission requiring its own full design-and-approval cycle — not something this build, or any future work citing it, may skip.
- **Status (card_level 1) is deliberately excluded**, even though it also produces no card today — it remains a human-facing "awareness only" tier per `MANAGER.md` §9, not something doctrine ever named as safe for a future automated system to see through this interface.
- **No authentication on this route**, matching `/manager`'s own boundary — it exposes strictly less detail than the already-ungated `/manager` page (aggregate counts of the single lowest-risk tier, nothing else).

---

*End of STAGE12_MANAGER_M7_POLICY_HOOK_WALKTHROUGH_REPORT_v1.*
