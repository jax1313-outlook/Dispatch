# DISPATCH_COMPLETION_BLUEPRINT

> **SUPERSEDED 2026-08-26 by `docs/readiness/COMPLETION_BLUEPRINT_v2.md`.**
>
> Kept in full. It is not wrong — it is a plan written before anything had run on Mike's
> machine, and its stage order survived contact. What it could not anticipate is that every
> defect which actually blocked use on 2026-08-25 fell outside it: a launcher nobody could
> find, no way to create a sign-in, an error page that explained nothing. v2 adds the stage
> this document had nowhere to put.
>
> Per `DECISION_LOG.md`: superseded decisions are marked, not edited away.


**Phase 13 deliverable — sequenced, narrow, verifiable build missions**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**Status:** Proposed. **No mission here is authorized.** Mike approves missions individually, never
as a block. A mission may not be widened after approval; a mission needing more than its stated
scope stops and returns for a new approval.

Every mission below carries the standing artifact rule: **source files, a commit, a remote branch, a
pull request, behavioral tests, exact test output, a reviewer disposition, and Mike's acceptance or
rejection.** An internal sandbox path is not delivery. A completion report is not delivery. A list
of test names is not verification.

---

## STAGE 0 — Artifact ownership and repository recovery

### OWN-01 · Prove the delivery path to Mike's machine
- **Problem:** No proven path from an approved merge to Mike's operational copy. "Mike owns Dispatch" is unverified.
- **Files affected:** none — `DEPLOY_LOCAL.md` may gain a verification note.
- **New files allowed:** none.
- **Dependencies:** none. **This is first.**
- **Scope:** Mike, on Windows: `git clone` → `pip install -e .` → `cin-portal-init-admin` → `python portal/app.py` → log in → create one load → stop → restart → confirm the load persists. Record each step's output.
- **Exclusions:** no code change; no `bootstrap_d_drive.py` run until this passes.
- **Tests:** none — this is an execution proof, not code.
- **Acceptance evidence:** Mike's own terminal transcript showing the load present after restart.
- **Rollback:** n/a.
- **Builder:** **Mike Zachary personally.** Cannot be delegated.
- **Reviewer:** Mike.

### OWN-02 · Consolidate governance into the Dispatch repository
- **Problem:** 20 doctrine documents live in Claude-3/Jules, not with the code they govern; `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` is cited by 4 files and exists nowhere.
- **Files affected:** `portal/models/identity.py`, `portal/app.py`, `portal/routes/auth.py`, `tests/test_portal.py` (citation text only).
- **New files allowed:** `governance/*.md`, `governance/SUPERSESSION_MAP.md`.
- **Dependencies:** OWN-01.
- **Scope:** copy the documents in; write one supersession map naming the current version of each; either locate the missing PIN-scope document or amend the 10 citations to point at what actually exists.
- **Exclusions:** **do not edit any doctrine text.** Move and index only.
- **Tests:** a structural test asserting every governance document cited by a `.py` file exists on disk.
- **Acceptance evidence:** that test passing; the supersession map reviewed by Mike.
- **Rollback:** documents are additive; revert the commit.
- **Builder:** Claude Code. **Reviewer:** Mike.

### OWN-03 · Adjudicate the two portals
- **Problem:** Two implementations both claim to be Dispatch. Jules has no persistence and no auth; Dispatch has both.
- **Files affected:** none in Dispatch.
- **New files allowed:** `DECISION_LOG.md` entry.
- **Dependencies:** OWN-01.
- **Scope:** Mike names one portal as the product; the other is archived read-only. Recommendation on the evidence: **Dispatch/portal/**.
- **Exclusions:** do not port Jules code in this mission.
- **Acceptance evidence:** a `DECISION_LOG.md` entry in Mike's words.
- **Builder:** **Mike.** **Reviewer:** Mike.

### OWN-04 · Remove the committed debugger PIN
- **Problem:** `Jules/flask_app.log` is a committed file containing `Debugger PIN: 631-326-424` for an app that ran with debug on, bound to `0.0.0.0`, with no authentication.
- **Files affected:** `Jules/flask_app.log`, `Jules/.gitignore`.
- **Dependencies:** none — **do this immediately, regardless of OWN-03.**
- **Scope:** delete the file, gitignore `*.log`, and treat the PIN as burned.
- **Exclusions:** history rewriting is out of scope unless Mike asks.
- **Acceptance evidence:** file absent from the working tree; `.gitignore` updated.
- **Builder:** Claude Code. **Reviewer:** Mike.

### OWN-05 · Restore the review record and prune branches
- **Problem:** PRs #113–#115 merged 718 lines of engine code and 7 doctrine-shaped documents with no `DECISION_LOG.md` entry and no walkthrough report. 54 stale remote branches.
- **Files affected:** `DECISION_LOG.md`.
- **Dependencies:** OWN-03.
- **Scope:** one Decision Log entry per merged PR recording what was accepted, or explicitly marking it unreviewed; delete merged remote branches.
- **Exclusions:** do not retroactively approve anything on Mike's behalf.
- **Builder:** Claude Code drafts; **Mike dispositions.**

## STAGE 1 — Runtime and persistence stabilization

### RUN-01 · Refuse to start on a default secret
- **Problem:** S-1 and S-3. `DISPATCH_EMAIL_SECRET` defaults to `"dispatch-dev-secret"`; `PORTAL_SECRET_KEY` defaults to a published string and only warns.
- **Files affected:** `portal/config.py`, `dispatch/notifications.py`, `cin_lite/email_delivery.py`, `portal/app.py`.
- **Scope:** outside `TESTING`, both secrets must be set or `create_app()` raises. Keep the deterministic test defaults so the suite is unaffected.
- **Exclusions:** do not change the token format — that is RUN-02.
- **Tests:** app refuses to start with each secret unset; app starts with both set; every existing test still passes.
- **Acceptance evidence:** full suite green plus the new refusal tests; a manual start with the variables unset showing the refusal.
- **Rollback:** single-commit revert.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-02 · Give stakeholder tokens an expiry and a revocation path
- **Problem:** S-2. `HMAC(secret, "dispatch-stakeholder:" + load_id)` is valid forever.
- **Files affected:** `dispatch/notifications.py`, `portal/routes/stakeholder.py`, `portal/routes/dispatch_api.py` (link generation).
- **Scope:** add an issued-at and an expiry to the signed payload; verify both; return the existing `403` on expiry. Add a per-load revocation counter in the signed material so a link can be killed without rotating the global secret.
- **Exclusions:** no change to what `build_stakeholder_view()` discloses.
- **Tests:** valid token passes; expired token 403s; revoked token 403s; the IDOR check still holds; existing 33 stakeholder tests pass.
- **Acceptance evidence:** exact suite output.
- **Rollback:** old-format tokens stop working — confirm with Mike that none are live (see OWN-01).
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-03 · Session cookie policy
- **Problem:** S-5.
- **Files affected:** `portal/config.py`.
- **Scope:** set `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE` from an env flag, and a `PERMANENT_SESSION_LIFETIME`.
- **Exclusions:** no change to the gate logic.
- **Tests:** cookie flags asserted on a real response; session expiry asserted.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-04 · CSRF protection on all mutating routes
- **Problem:** S-4. 109 of 218 routes mutate under cookie auth with no CSRF token.
- **Files affected:** `portal/app.py`, all 8 route modules, all form templates.
- **Scope:** one CSRF mechanism, applied app-wide, exempting only the two token-authenticated blueprints and `dispatch_api.dispatch_decision` — **the same exemption list the login gate already uses, and no wider.**
- **Exclusions:** do not add a dependency without Mike's approval; a stdlib implementation is acceptable.
- **Tests:** each exempt endpoint still works without a token; a representative mutating route in each blueprint rejects a missing/incorrect token; all 1,162 existing HTTP tests pass.
- **Acceptance evidence:** exact suite output. **This is the largest-blast-radius mission in Stage 1 — expect it to touch every template.**
- **Rollback:** single revert; the mechanism is additive.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-05 · Backup and restore procedure
- **Problem:** D-1. No backup exists for the SQLite DB and 11 JSON stores.
- **New files allowed:** `scripts/backup.py`, `scripts/restore.py`, `BACKUP_AND_RECOVERY.md`.
- **Scope:** a single command that produces a timestamped archive of the data directory using SQLite's own backup API (not a file copy of a live WAL database), and a restore command that refuses to overwrite a non-empty target without an explicit flag.
- **Exclusions:** no cloud storage, no scheduling, no encryption in this mission.
- **Tests:** backup then restore into an empty directory reproduces every load, activity and JSON store byte-for-byte; restore refuses a populated target without the flag.
- **Acceptance evidence:** exact suite output **plus Mike performing one restore on his own machine.**
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-06 · Label sample and test data
- **Problem:** D-3, D-4.
- **Files affected:** `dispatch/acquisition.py`, `portal/templates/dispatch.html`.
- **Scope:** when the acquisition source is the bundled sample directory, mark every produced load with an explicit `source="SAMPLE"` and render a visible badge. Do not silently serve samples as real.
- **Exclusions:** do not delete `portal/sample_dispatch_data/`.
- **Tests:** sample-sourced loads carry the marker; a configured real source does not; the badge renders.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-07 · Schema version and migration ledger
- **Problem:** D-2.
- **Files affected:** `dispatch/db.py`.
- **Scope:** a `schema_version` table; each migration recorded; startup refuses a database newer than the code.
- **Exclusions:** no down-migrations in this mission; no change to any existing table.
- **Tests:** fresh DB stamps the current version; an existing DB migrates once and is idempotent on a second run; a future-versioned DB is refused.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-08 · Storage directories under a WSGI server
- **Problem:** S-7. `_ensure_storage_dirs()` runs only under `__main__`.
- **Files affected:** `portal/app.py`.
- **Scope:** call it from `create_app()`, guarded so tests are unaffected.
- **Tests:** directories exist after `create_app()` with the root variables set.
- **Builder:** Claude Code. **Reviewer:** Mike.

### RUN-09 · Fix the coverage gate
- **Problem:** D-7. CI measures 14 % of production.
- **Files affected:** `.github/workflows/ci.yml`.
- **Scope:** drop the `--cov=cin_lite` override so `.coveragerc`'s `source = cin_lite, dispatch` governs; set `--cov-fail-under` to the **measured current value**, not an aspiration, so the gate ratchets rather than fails on day one.
- **Exclusions:** do not add tests in this mission; do not raise the threshold beyond what is measured.
- **Acceptance evidence:** the CI run output showing the new measured percentage.
- **Builder:** Claude Code. **Reviewer:** Mike.

## STAGE 2 — Core Spine truth and state control

### SPINE-01 · Adjudicate the Opportunity lifecycle against BM-10
- **Problem:** `dispatch/opportunities.py` introduces a third state machine on `main` with no Decision Log entry, against standing constraint BM-10.
- **Files affected:** none until Mike rules.
- **Scope:** produce the mapping from the 9 lifecycle stages onto the existing load-status model and the work-item model, and present the three options — map in, adopt with an explicit BM-10 amendment, or revert. **Recommendation: map in or adopt; do not revert — the modelling is sound, only the governance is missing.**
- **Exclusions:** **do not wire anything** until this is decided.
- **Acceptance evidence:** a `DECISION_LOG.md` entry in Mike's words.
- **Builder:** Claude Code drafts. **Reviewer and decider: Mike.**

### SPINE-02 · C1 — retire the duplicate mission-state copy
- **Problem:** load status is stored twice.
- **Files affected:** `portal/models/sandbox.py`, `portal/routes/pages.py:989-992`, `portal/routes/api.py:494,509`, `portal/templates/dispatch.html:403`, `portal/templates/brief.html:137`.
- **Scope:** the approved read-through design — the sandbox entry keeps `engine_load_id` and reads status through it.
- **Exclusions:** removing `engine_load_id`; any identifier change (BM-11); any change to the sandbox lifecycle or HOLD sweep.
- **Tests:** no stored copy of load status outside `loads.status`; both display paths still render it; a structural test forbids reintroduction.
- **Rollback:** medium risk — two display paths read the copy today. Revert restores it.
- **Builder:** Claude Code. **Reviewer:** Mike.

### SPINE-03 · C2a — retire or rename `/calendar`
- **Problem:** Dispatch presents a calendar; Outlook must be the only calendar.
- **Files affected:** `portal/routes/pages.py:310`, `portal/templates/calendar.html`, `portal/templates/base.html`, `portal/routes/dispatch_api.py` (`/calendar` API).
- **Scope:** **one** of retire outright, or rename to a non-calendar operational view. **Mike chooses which.**
- **Exclusions:** any Outlook integration; any capacity computation; C2a must not silently become the Visual Capacity Board.
- **Tests:** no route, template or navigation entry presents a calendar; 16 existing `test_load_calendar.py` tests updated to the chosen outcome, not deleted.
- **Builder:** Claude Code. **Reviewer:** Mike.

### SPINE-04 · C4 — replay guards for the 15 unguarded side-effect sites
- **Problem:** duplicate stall notifications and duplicate checkpoint emails are possible; this is a precondition for any unattended operation.
- **Files affected:** `dispatch/services.py`, `dispatch/notifications.py`.
- **New files allowed:** an execution-ledger module.
- **Scope:** extend the existing guard mechanism to the 15 sites enumerated in `DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1` §8.
- **Exclusions:** **any scheduler (BM-12)**; any retry policy; halt-and-raise semantics — that posture is undecided.
- **Tests:** each guarded effect invoked twice produces one effect and one ledger entry; the ledger survives restart; **assertions are on the ledger, never on the outbox** — the outbox filename is deterministic and overwrites, so an outbox assertion passes even when two real sends occurred.
- **Builder:** Claude Code. **Reviewer:** Mike.

### SPINE-05 · Stop auditing no-op status changes
- **Problem:** P-13. `update_load()` writes `"Status changed from dispatched to dispatched"`.
- **Files affected:** `dispatch/services.py` (one guard), `tests/test_status_change_audit.py`.
- **Scope:** one line, making all four status paths identical.
- **Exclusions:** do not alter existing stored entries.
- **Tests:** the existing tests that pin current behavior are updated to pin the new behavior; no other test changes.
- **Builder:** Claude Code. **Reviewer:** Mike.

## STAGE 3 — Operational engine hardening

### ENG-01 · Remove optimistic defaults from Dynamic Capacity
- **Problem:** `stacking_policy` defaults to `"STACKABLE"`, `allows_top_load` to `True`, `TruckArrangement.is_stackable` to `True`, `apply_asset_profile(verified_by="Mike Zachary")` stamps Mike as verifier by default, and `set_verified_hos(source="ELD_LOG")` names an integration that does not exist.
- **Files affected:** `dispatch/capacity.py`, `dispatch/truck_arrangement.py`, `tests/test_architecture_discoveries.py`.
- **Dependencies:** **SPINE-01 must be decided first.**
- **Scope:** every unknown defaults to `UNKNOWN`; `verified_by` has no default; `set_verified_hos` requires an explicit source and refuses `"ELD_LOG"` while no ELD integration exists.
- **Exclusions:** do not wire the module into anything in this mission.
- **Tests:** a freshly constructed capacity object is `UNKNOWN` on every dimension it has not been told about; `can_accommodate` returns `False` with `NEEDS_REVIEW` for each.
- **Builder:** Claude Code. **Reviewer:** Mike.

### ENG-02 · Correct the STALE-configuration feasibility path
- **Problem:** `can_accommodate()`'s final expression returns feasible when every reason is a `NEEDS_REVIEW` containing the word "stale" — so a **STALE asset configuration** yields `True`, not just a stale HOS snapshot under simulation.
- **Files affected:** `dispatch/capacity.py:338`.
- **Dependencies:** SPINE-01, ENG-01.
- **Scope:** the stale-tolerant branch applies **only** to `hos_status == "STALE"` under `is_simulation=True`, never to `configuration_status`.
- **Tests:** stale configuration is infeasible; stale HOS under simulation stays feasible; stale HOS outside simulation is infeasible.
- **Builder:** Claude Code. **Reviewer:** Mike.

### ENG-03 · Route Risk must not report "achievable" with no data
- **Problem:** with no events recorded, `get_route_risk()` returns `available: False` **and** `delivery_commitment_status: "achievable"` — an unknown presented as a positive fact.
- **Files affected:** `route_risk/engine.py:144`, `dispatch/store.py`, `portal/templates/driver_home.html`.
- **Scope:** the no-data path returns `"unknown"`; consumers render it as unknown.
- **Exclusions:** no change to the consequence-level model or COMI thresholds.
- **Tests:** no-data path returns `unknown`; a recorded event still returns its own value; the driver page renders the unknown state.
- **Builder:** Claude Code. **Reviewer:** Mike.

### ENG-04 · Map visual must not default to available
- **Problem:** `has_map_visual` defaults to `True`, producing `map_visual_placeholder.available = True` for a placeholder with no map behind it.
- **Files affected:** `route_risk/engine.py:32,83`, `dispatch/services.py:371`, `dispatch/store.py`.
- **Scope:** default to `False`; `available` becomes true only when a real visual exists, which today is never.
- **Tests:** default event reports no map visual; the 20 durability tests pass.
- **Builder:** Claude Code. **Reviewer:** Mike.

## STAGE 4 — Portal wiring

### PORTAL-01 · Driver proof-of-delivery capture
- **Problem:** T2-1. The Driver Portal cannot write anything. Under Driver-First Doctrine this is the largest gap in the program.
- **Files affected:** `portal/routes/driver_portal.py`, `portal/templates/driver_home.html`.
- **Dependencies:** RUN-04 (CSRF), RUN-03.
- **Scope:** one control per active load — "Delivered: attach photo" — posting to a **new driver-scoped endpoint** that calls the existing `services.attach_evidence()` and `services.add_milestone()`. Driver identity comes from `session["driver_id"]`; a driver may only act on a load assigned to them.
- **Exclusions:** no load editing; no status override; no bypass of the M1 transition gate — **a refused transition must still refuse for a driver**; no new evidence model.
- **Tests:** a driver attaches evidence to their own load and it appears in Authority views; a driver cannot touch another driver's load (404, not 403); a refused transition still refuses and returns the 409 shape; the evidence checksum verifies.
- **Acceptance evidence:** exact suite output plus a manual walkthrough on a phone-width viewport.
- **Rollback:** additive endpoint; revert removes it.
- **Builder:** Claude Code. **Reviewer:** Mike.

### PORTAL-02 · Driver proof-of-pickup capture
- Same shape as PORTAL-01, for the pickup milestone. **Separate mission, separate approval** — do not fold it into PORTAL-01.

### PORTAL-03 · Driver load lookup
- **Problem:** T2-2. `/search` exists but is Authority-gated.
- **Files affected:** `portal/routes/driver_portal.py`, new template.
- **Dependencies:** PORTAL-01.
- **Scope:** a driver-scoped lookup returning **only** loads assigned to that driver, reusing the existing search service.
- **Exclusions:** no access to unassigned loads; no financial fields.
- **Tests:** a driver finds their own load; a driver cannot find another driver's load; no rate, margin or settlement field appears in the response.
- **Builder:** Claude Code. **Reviewer:** Mike.

### PORTAL-04 · Current Mission priority on the driver surface
- **Problem:** T2-3. All active loads render as equal cards.
- **Files affected:** `portal/templates/driver_home.html`, `portal/routes/driver_portal.py`.
- **Scope:** the mission nearest its next expected milestone renders first and larger; the rest collapse.
- **Exclusions:** **no new state, no new field, no scoring** — ordering only, computed at render time.
- **Tests:** ordering is deterministic given fixed timestamps; a single-load driver sees no change.
- **Builder:** Claude Code. **Reviewer:** Mike.

## STAGE 5 — Outlook and external integrations

**No mission is proposed in this stage.** The Outlook integration decision has not been made, and
doing nothing keeps Outlook authoritative, which is doctrinally correct. When Mike decides, the
first mission is scoped as: *create an Outlook event only after a human-authorized load commitment,
one-way, Dispatch never reads back.* It is written here so the shape is agreed in advance, not so it
can be started.

## STAGE 6 — Operational pilot readiness

### PILOT-01 · One real load, end to end, recorded
- **Dependencies:** every Stage 0–2 mission accepted.
- **Scope:** Mike runs one real load through Dispatch: enter, assign, dispatch, milestone by milestone, evidence, delivery, rate confirmation, settlement, invoice, archive. **Every point where he had to leave Dispatch or distrust a number is written down.**
- **Acceptance evidence:** Mike's own record of the run.
- **Builder:** **Mike.** **Reviewer:** Mike.

### PILOT-02 · Disposition the pilot findings
- Convert PILOT-01's notes into the next mission set. Nothing further is planned before this exists.

## STAGE 7 — Scale readiness

Not scoped. Tier 4 of the workable-product definition lists its contents. **No mission in Stage 7
may be started while any Stage 0 mission is open.**
