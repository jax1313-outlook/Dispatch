# PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1

Program: Dispatch
Status: **IMPLEMENTED.** Scope approved and executed on `dispatch/portal-authentication-pin`,
merged to `main` via PR #84 (squash commit `fcad6145`), exactly as scoped below. Required a
follow-up commit (`ee4f200`, included in the same PR) fixing a CI regression the initial push
missed — see the note at the end of this document.
Origin: Track E of the closed `DISPATCH_INTEGRITY_AND_DEPLOYMENT_VERIFICATION_MISSION_v1` found
Portal has no authentication of any kind (Finding #1). Mike reviewed the option set and decided:
build the `DISPATCH_PIN` authentication scheme already specified in
`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` (found in the `Jules-3`/`Claude-2`
doctrine-review repos this session — real, detailed, never implemented). This document scopes a
minimal first build against that specification, against `jax1313-outlook/Dispatch`'s real Portal
code, the same way every other implementation this session was scoped before being approved.
Rule: No code changes authorized by this document. Do not implement until scope is approved,
matching every prior stage this session (Stage 1, Stage 2, the presentation-layer panel).

---

## 0. What The Full Specification Contains, And Why This Scope Is Narrower

`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` (read in full) specifies: four roles (Authority,
Driver, External Viewer, System Service), a full PIN lifecycle (create/assign/validate/change/
reset/revoke/lockout), a session model, a permission model, an approval-event audit schema, a
12-category security-boundary map across every department, and a 12-entry security event catalog
feeding into Monday/Monthly reporting.

Building all of that at once would repeat the mistake this session already corrected for
(Publisher/Library/Intelligence attempted-full-contract overreach). Following the same pattern
Stage 1 and Stage 2 used — narrow first slice, defer the rest explicitly, don't silently drop it —
this scope covers **only** what's needed to close Track E's Finding #1: Portal is completely
unauthenticated today. Everything else in the spec is named below as deferred, not abandoned.

## 1. Which role(s) does this build cover?

**Authority only.** The real Portal (`portal/templates/`) has no segmented driver-facing or
external-facing views today — `driver_detail.html`/`driver_pay.html` are dispatcher-facing pages
*about* drivers (freight-domain records), not a driver login surface. Building Driver or External
Viewer roles now would mean inventing access boundaries for pages that don't yet distinguish who's
allowed to see them, which is a separate, larger scoping question. System Service isn't a login
role at all (spec Section 3.4 — it's for deterministic background activity, not a human session).

**Deferred, not decided against**: Driver and External Viewer roles, and the permission
segmentation they'd require across existing templates. A future scope, if pursued.

## 2. What does the identity/PIN record contain, and where does it live?

Minimum fields per spec Section 2.1/4.1, trimmed to what a single-role build needs:
`user_id`, `display_name`, `role` (fixed to `"Authority"` for this build), `status`,
`pin_hash`, `created_at`, `updated_at`, `last_login_at`, `failed_attempt_count`,
`locked_until`.

**Storage: a new, dedicated module — not Library.** The specification itself makes Library
storage conditional ("if Mike chooses to," Section 11), not a default. Retrofitting Library's
existing `SECTIONS`/`add_record()` shape to hold credential material would mean either expanding
Library's real contract (out of scope, same constraint Stage 1 operated under) or bypassing its
review/approval gate entirely for a use case it wasn't designed for. A new
`portal/models/identity.py`, structured like every other department model in this codebase
(`library.py`, `publisher.py`, `intelligence.py`), keeps the same file-per-department pattern
without forcing PIN records into a department whose real schema has no concept of them. If Mike
wants PIN records under Library governance later, that's Section 11's conditional path — a
separate future decision, not assumed here.

**PIN storage format**: hashed, never plaintext, using `werkzeug.security.generate_password_hash`/
`check_password_hash` — already a transitive Flask dependency, no new library needed, satisfies
spec Section 17's "no plaintext PINs" requirement directly.

## 3. How does the very first Authority identity get created?

A bootstrap problem: no authenticated Authority user exists yet to create the first one through a
protected route. Minimum viable answer: a one-time CLI command (`cin-portal init-admin` or
equivalent, added to `[project.scripts]` alongside the existing `dispatch`/`cin-portal`/`cin-sync`
entries) that prompts for a PIN directly at the terminal — run once, on the server, by Mike,
never through this chat, matching the pattern just established fixing `DISPATCH_EMAIL_SECRET`.
Refuses to run if an Authority identity already exists, so it can't be used to create a second
one by accident or by someone else with server access.

## 4. What does session/login actually look like?

Reuses Flask's existing session mechanism (`portal/config.py`'s `SECRET_KEY`, currently
`PORTAL_SECRET_KEY` — see Track E Finding #5, a related, currently-open item: this needs to be a
real, non-default value on the live VPS for session cookies to be trustworthy at all, checked and
fixed the same way `DISPATCH_EMAIL_SECRET` was). A new `/login` route accepts a PIN, validates
against the stored hash, and on success sets `session["user_id"]`, `session["role"]`. A
`before_request` hook on the Portal blueprint(s) checks for a valid session and redirects to
`/login` if absent — this is the specific gap Track E's Finding #1 named directly ("no
`before_request` gate").

**Deferred**: the full session-record schema from spec Section 5 (`session_id`,
`permissions_snapshot`, etc.) — a minimal build only needs the session to answer "is someone
logged in and what's their role," not the full audit-grade session object. That richer session
model is worth building when Driver/External Viewer roles are, since permission snapshots only
matter once there's more than one permission set to distinguish.

## 5. What happens on repeated failed attempts?

Deterministic, per Rule 9: **5 failed attempts locks the identity for 15 minutes**
(`locked_until` timestamp, checked before PIN validation runs). Fixed numbers chosen for a
single-Authority build where there's no lockout-review workflow to route to yet — spec Section
4.3's "Manager / Authority review depending on final implementation rules" is deferred, since
Manager stays dormant (per the standing Manager Preservation Decision) and there's no second
Authority user to review a lockout anyway in this build.

## 6. What gets logged, and where?

Minimum security events per spec Section 16, trimmed to what's decidable without the full audit
infrastructure: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `SESSION_CREATED`, `PIN_CHANGED`. Written to a
plain append-only log file (`portal/data/security_events.jsonl` or equivalent), not a new
database table — matches this codebase's existing lightweight JSON-file storage pattern
(`conflicts.json`, `sandbox.json`) rather than introducing new infrastructure for a first build.

**Deferred**: the remaining 8 event types (`PIN_CREATED`, `PIN_RESET`, `PIN_REVOKED`,
`SESSION_EXPIRED`, `AUTHORITY_ACTION_APPROVED`, `AUTHORITY_ACTION_REJECTED`, `PERMISSION_DENIED`,
`SUSPICIOUS_ACTIVITY`) and any Monday/Monthly report integration (spec Section 15) — those event
types mostly presuppose multiple roles or an approval-event schema this build doesn't create yet.

## 7. What about the existing `approved_by` fields in Publisher/Library/Archive?

**Out of scope, not touched.** Those already work via `RESERVED_SYSTEM_IDENTITIES` and a
human-typed name — real, functioning gates verified in Track D. A future stage could wire
`approved_by` to the now-real logged-in identity instead of a free-text prompt (closing the gap
where the string "Mike Zachary" is typed, not verified), but that's a separate change to three
existing approval flows, not part of standing up login itself. Flagged for a later scope, not
silently dropped.

## 8. What test proves this works?

1. Bootstrap creates exactly one Authority identity; running it twice refuses.
2. Correct PIN on `/login` → session created → a previously-blocked page now loads.
3. Wrong PIN → no session, `LOGIN_FAILURE` logged, failed-attempt counter increments.
4. 5th wrong attempt → identity locked, correct PIN rejected until `locked_until` passes.
5. No session at all → every real Portal page redirects to `/login` (the actual
   `before_request` gate working, not just the login route in isolation).
6. PIN stored as a hash, never as plaintext, anywhere on disk — direct check of the identity
   record on disk after creation.

## Summary: What This Scope Actually Builds

1. `portal/models/identity.py` — a new, minimal identity/PIN store. One role (`Authority`).
   Hashed PINs, failed-attempt lockout.
2. A bootstrap CLI command to create the first (and, in this build, only) Authority identity.
3. `/login` route plus a `before_request` gate protecting the rest of Portal.
4. A minimal append-only security-event log (4 event types).
5. Tests per Section 8, above.

**Explicitly not built here, and not abandoned** — each is its own future scope if pursued:
Driver and External Viewer roles and their permission segmentation; the full session/permission-
snapshot model; PIN self-service change/reset workflow; the remaining 8 security event types and
report integration; wiring `approved_by` to the real logged-in identity; storing PIN records
under Library governance (spec Section 11's conditional path).

**One live prerequisite, not part of this build but blocking its real-world security**: Track E's
Finding #5 (`PORTAL_SECRET_KEY` unconfirmed on the live VPS) should be checked and, if needed,
fixed before or alongside deployment of whatever this scope produces — a PIN system is only as
strong as the session mechanism underneath it.

## Execution Note: A CI Regression Found And Fixed Before Merge

The first push (commit `4d327c8`) passed locally but failed CI on all three Python versions —
820 failed, 34 errors. The local pre-push run only covered `tests/test_portal.py`; this repository
has 67 test files that instantiate the Portal app, most previously unknown to this scope. The
new global `before_request` login gate applies to the entire app, and most of those other files'
own `app`/`client` fixtures had no way to opt out, so their real routes started redirecting to
`/login` instead of doing what their tests expected.

Root cause, once found: a first attempted fix (computing a `LOGIN_DISABLED` default once, inside
`create_app()`, based on the config dict passed at creation) missed the majority case — 59 of the
67 files call `create_app()` with no config dict at all and set `app.config["TESTING"] = True` on
the returned app object afterward, which is too late for a creation-time default to see. The
actual fix (commit `ee4f200`) checks `TESTING`/`LOGIN_DISABLED` live, on every request, instead of
snapshotting a default once — this reflects whatever's actually on `app.config` by request time
regardless of when or how it got there, so none of the 67 files needed individual changes.

Full suite verified clean before the second push: 0 failed, 0 errors, exit 0, across all 67 files
— not just `tests/test_portal.py`. CI confirmed green on all three Python versions afterward.

Mike decides.
