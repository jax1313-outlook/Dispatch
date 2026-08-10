# STAGE7_SECURITY_FOUNDATION_WALKTHROUGH_REPORT_v1

## Identity, PIN, Session, Role, Audit, Approval Events (capability), Security Sub-Library (mechanism)

**Status:** Implemented and verified. Branch: `stage7-security-foundation` (based on `stage5-portal-reconciliation`).

**Responds to:** Mike's "Approve Stage 7 build," followed by the Stage 7 Design Review that narrowed scope (no blanket Portal-wide gating; Security Foundation only), and "Approve design" on the revised `DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md`.

---

## What Changed

1. **`dispatch/security/`** (new package: `models.py`, `db.py`, `store.py`, `auth.py`) — Identity (`User`), PIN (`PinRecord`, PBKDF2-HMAC-SHA256 at 600,000 iterations, distinct from `cin_lite/archive.py`'s file-integrity SHA-256), Session, Role (`Authority`, `Driver`, `External Viewer`, `System Service` — the four roles from the Security and Authentication Specification), and Audit (`SecurityEvent`, nine event types). `users`, `pin_records`, `sessions`, `security_events` tables live in the same `dispatch.db` file, same connection, same idempotent-schema pattern Stage 4 established for the Spine — wired into `dispatch/db.py`'s `_init_db()` alongside `init_spine_schema()`.
2. **`portal/auth_helpers.py`** (new) — Flask-specific glue: `get_current_session()`/`get_current_user()` (cached on `flask.g` per request), `login_required` (any valid session), `authority_required` (Authority role only, logs `PERMISSION_DENIED` on refusal). Deliberately kept out of `dispatch/security/`, which has no Flask dependency, mirroring how `dispatch/spine/` has no Portal dependency.
3. **`portal/routes/security.py`** (new) — `/login` (GET/POST) and `/logout` (GET/POST). Login failure ("unknown identity" vs. "wrong PIN") returns the same generic error and writes the same `LOGIN_FAILURE` event either way, so the response can't be used to enumerate valid identities.
4. **`portal/routes/pages.py`** — `/settings` gated with `@authority_required`. This is the **only** existing route this build modifies to require a session.
5. **`portal/app.py`** — a context processor injects `current_dispatch_user` into every template for the nav indicator. Purely informational: it never blocks rendering or redirects.
6. **`portal/templates/base.html`** — sidebar shows "Logged in as {name} (Logout)" or "Login," rendered from the context processor above.
7. **`portal/templates/login.html`** (new), **`portal/static/style.css`** (`.sidebar-auth`).
8. **`tests/test_security_foundation.py`** (new) — 29 tests.

## What Did Not Change

Every Portal page besides `/settings` — Home, Search, SAM, Dispatch, Calendar, Fleet, Exceptions, Billing, Profitability, IFTA, Fuel Estimator, Compliance, Brokers, Publisher, Library, Archive, Intelligence, Pipeline, Queues, Conflict Notices, Driver Pay, Email Templates — renders exactly as before, unauthenticated, unchanged. No existing action route (`/api/action`, `/api/inquiry/*`, `/api/publisher/*`, `/api/conflict/resolve`, `/api/library/*`, `/api/archive/create`, `/api/intelligence/add`, `/api/dispatch/*`) was modified to require login. The three existing HMAC-token email-approval gates (CIN/SAM decision, dispatch-load decision, IFTA quarter approval) are untouched — no file under `cin_lite/` or the IFTA engine was modified in this build. The phone approval workflow is untouched. `dispatch/spine/` (Stage 4) and `portal/models/sandbox.py`/`conflict.py` (Stage 5) are untouched.

## Scoping Notes (Flagged, Not Silent)

- **Approval Events gets a capability, not a mandate.** The design named Approval Events as in-scope for Security Foundation. What's built is the *capability* — when a real session exists, `dispatch.spine.store.create_approval_event()` can be populated with real `session_id`/`user_id`/`role` — proven directly by a test that manually builds a session and an `ApprovalEvent`. No existing action route (Book, Pursue, Publisher approve, etc.) was changed to require login or to pass real identity. Wiring identity into those routes is Portal-Wide Enforcement territory, not this stage.
- **Security Sub-Library re-check is mechanism only.** `require_security_sublibrary_pin()` is built and tested (reuses `validate_pin()` and the `pin_records` table — one PIN system, a second trigger point) but is not called from any route, because there is no "security" Library section to protect yet; that depends on Stage 9's Library `origin` field.
- **Architectural deviation from the design document's literal path.** The design specified `portal/security/`. While wiring `dispatch/db.py`'s schema init, this would have required `dispatch/db.py` to import from `portal/`, inverting the codebase's established one-directional dependency (`portal/` depends on `dispatch/`, never the reverse — true of every other file, e.g. `portal/routes/pages.py` imports `from dispatch import services`). Corrected by placing the module at `dispatch/security/`, mirroring `dispatch/spine/`'s placement exactly. Routes and templates (the actual Flask-facing login/logout UI) remain under `portal/` as `portal/auth_helpers.py` and `portal/routes/security.py`. Functionally identical to the design's intent; only the package path differs.
- **No session expiry window.** `current_session()` treats `status == 'active'` as sufficient; there is no time-based timeout in this build. Session expiry is a reasonable Portal-Wide Enforcement-era refinement, not required for Security Foundation's narrow scope.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_security_foundation.py` — **29 passed, 0 failed.**
- Full suite: `python3 -m pytest -q` from the repo root — **2,402 tests, 0 failures, 0 errors** (2,373 from before Stage 7 + 29 new).
- **Two pre-existing tests needed updating, not the security code.** Gating `/settings` behind `@authority_required` is exactly what the approved design calls for, but it meant `tests/test_portal.py::TestPageRendering::test_settings_renders` and `tests/test_dashboard_enhancements.py::TestSettingsStallThresholds` (2 tests) previously hit `/settings` unauthenticated and asserted a 200. Fixed by adding a shared `login_as_authority` fixture to `tests/conftest.py` that creates a fresh Authority user and logs the test client in via the real `/login` route before those three tests hit `/settings` — exercising the real gate rather than bypassing it. No production code changed to make these pass.

## Live Walkthrough

Run against a live Flask dev server (`python -m portal.app`, `PORTAL_DATA_DIR`/`DISPATCH_OPERATIONS_ROOT` pointed at a throwaway temp directory — never real production data) on `127.0.0.1:8091`.

```
GET  /home                                    -> 200 (unauthenticated, unchanged)
GET  /library                                 -> 200 (unauthenticated, unchanged -- informational browsing)
GET  /settings                (no session)    -> 302 Location: /login?next=/settings
GET  /login                                   -> 200 (form renders)

POST /login  display_name=Mike pin=0000 (wrong)      -> 200, "Invalid identity or PIN."
POST /login  display_name=Mike pin=4471 (correct)    -> 302 Location: /home, session cookie set

GET  /settings  (Mike's session, Authority role)     -> 200, "SAM.gov API" present,
                                                          nav shows "Logged in as Mike"
GET  /logout                                          -> 302 Location: /login, session revoked
GET  /settings  (post-logout, same cookie)            -> 302 Location: /login?next=/settings

-- role check --
Created Dana (Driver role). Logged in successfully.
GET  /settings  (Dana's session, Driver role)         -> 403 "Forbidden — Authority role required."

-- existing action route unaffected --
POST /api/action  (no session, unknown sandbox_id)    -> 404 (app-level not-found, not an
                                                          auth redirect -- proves this route
                                                          was never gated)

-- audit trail --
security_events for the walkthrough session, in order:
  PIN_CREATED, LOGIN_FAILURE (wrong PIN), LOGIN_SUCCESS, SESSION_CREATED,
  PERMISSION_DENIED (Dana on /settings)
```

Every scenario behaved exactly as the revised design specifies: informational pages are unaffected, `/settings` is the only page gated, role enforcement rejects a non-Authority session with 403 rather than silently allowing or crashing, an existing unauthenticated action route is provably untouched, and every security-relevant event is written to the audit log. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **No session expiry.** A session stays valid indefinitely until explicit logout. Time-based expiry is deferred to Portal-Wide Enforcement, per the design's narrow scope for this stage.
- **`/settings` is the only enforcement point.** Every other page and action route is exactly as reachable, unauthenticated, as before this build — by design, not by omission. Portal-Wide Enforcement (broader page protection, wider access restrictions) remains a distinct, unapproved future stage.
- **PIN reset (`reset_pin()`) does not itself verify the approver's role.** It records who approved it (`approved_by_user_id`) but trusts the caller to have already confirmed that identity carries the Authority role — there is no Portal route calling this function yet, so this is inert until a future reset workflow is built and must check the approver's role at that call site.

---

*End of STAGE7_SECURITY_FOUNDATION_WALKTHROUGH_REPORT_v1.*
