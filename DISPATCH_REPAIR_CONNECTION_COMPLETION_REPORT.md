# DISPATCH_REPAIR_CONNECTION_COMPLETION_REPORT

**Maximum-Capacity Repair, Connection, Security and Durability Campaign**
**Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Date:** 2026-08-23 · **Authority:** Mike Zachary

---

## 1. Executive result

**CAMPAIGN RESULT: COMPLETE.** All six authorized workstreams are implemented. No unit was
blocked. No unit was deferred.

**Tests: 2,882 → 3,087, exit 0.** +205 net. **0 removed. 0 weakened** — three tests were rewritten
to assert a *stronger* property than before, each explained in §11.

The program that started this campaign had: a Dynamic Capacity engine connected to nothing and
stamping Mike's name on verifications nobody made; an Opportunity subsystem running a second
lifecycle and creating loads on its own authority; a signing secret published in the repository
that a deployment could silently start on; no backup of any kind; tokens that never expired and
could not be revoked; and no CSRF protection on 109 mutating routes.

All six are closed. The connected path — opportunity discovered → analysed against capacity →
presented → human decision → Spine transition → Current Reality → driver reports → stakeholder view
→ backed up and restored — is proven end to end in a single test that restores the load, the
milestone and the POD bytes out of a backup.

## 2. Workstreams completed

| | Workstream | Result | Tests |
|---|---|---|---|
| **A** | Dynamic Capacity integration and truth hardening (A1–A12) | **COMPLETE** — all twelve | 54 new + 10 updated |
| **B** | Opportunity lifecycle alignment (OPP-01…OPP-06) | **COMPLETE** | 32 new |
| **C** | Security hardening (C1–C5) | **COMPLETE** | 18 new |
| **D** | Backup and restore | **COMPLETE** | 38 new |
| **E** | Token expiration and revocation | **COMPLETE** | 34 new |
| **F** | CSRF protection | **COMPLETE** | 23 new |
| — | Cross-workstream integration | **COMPLETE** | 2 new |

## 3. Audit findings resolved

| Finding | Was | Now |
|---|---|---|
| **OT-4** `verified_by="Mike Zachary"` default | Any caller stamped a capacity profile as verified by Mike | `apply_asset_profile` has **no `verified_by` default** and requires an explicit `source`. No actor → `UNVERIFIED`, not `VERIFIED`. |
| **OT-5** `source="ELD_LOG"` default | Declared ELD-verified HOS with no ELD anywhere | `set_verified_hos` requires an explicit source **and** a timezone-aware `observed_at`; `set_hos_snapshot` is the honest intake |
| **OT-6** stale config reported feasible | `all(r.startswith("NEEDS_REVIEW") and "stale" in r…)` returned feasible for a **stale asset configuration** | Gone. `ASSET_CONFIGURATION_STALE` is a finding that requires review, in simulation too |
| **OT-1/2/3** optimistic cargo defaults | `STACKABLE`, `allows_top_load=True`, `is_stackable=True` | Unknown stays unknown. `is_stackable` is `None`-by-default, `arrangement_type` defaults to `"unknown"`, `securement_status="VERIFIED"` raises without a named actor |
| **S-1** published HMAC secret | Silent fallback to `dispatch-dev-secret` | Operational mode **refuses to start**. Development mode is opt-in, warns, and **pins the bind to loopback** |
| **S-2** tokens never expire, cannot be revoked | `HMAC(secret, "dispatch-stakeholder:"+load_id)`, valid forever | Signed payload with purpose, object, issued-at, expiry and nonce; per-token and per-object revocation; full audit |
| **S-3** published `SECRET_KEY` | Warning only | Same refusal as S-1 |
| **S-4** no CSRF on 109 mutating routes | `grep -rniE "csrf"` returned nothing | Session-bound synchronizer token on every mutating route; exemptions are exactly the login gate's |
| **S-5** no cookie policy | No flags, no expiry | `HttpOnly`, `SameSite=Lax`, env-gated `Secure`, 12-hour lifetime |
| **D-1** no backup | Nothing, anywhere, in seven repositories | SQLite backup API, JSON stores, uploads, archive, memory, redacted config; manifests, sha256, dry-run, safe destination |
| **CF-04** competing lifecycle authority | Opportunity owned a second state machine | Removed. Spine owns transitions; Opportunity requests them |
| **A11** candidate vs committed | Projected opportunities mutated the same fields as committed loads | `record_projected_opportunity` never touches `used_*`; `record_committed_load` requires `committed_by` **and** `authority_ref` |

## 4. Recoveries performed

None new — this campaign was repair, connection and build. The Spine (835 lines), the Driver
Transformation and the Archive Review Queue were recovered in the preceding Wave 1 and are the
foundation this campaign connected to.

## 5. Connections completed

| Was disconnected | Now |
|---|---|
| `dispatch/capacity.py` — 352 lines, referenced by nothing | Consulted by `OpportunityPipeline.analyze_opportunity`, feeding consumption metrics into scoring; stop-sequence evaluation folded into the main assessment |
| `dispatch/truck_arrangement.py` — 69 lines | `CargoUnit` with position, loading/unloading order, delivery sequence, access order and blocking; consumed by the capacity evaluation |
| `dispatch/opportunities.py` — 297 lines, own state machine | Correlated to Spine work items; every movement requested from Spine; commitment realised on the Spine side |
| Stop Sequence — a stop *count* | `Stop` records with appointment windows, service time, out-of-route and drive/duty impact, compared against remaining capacity |

## 6. Repairs completed

**A — Dynamic Capacity.** `can_accommodate` returned `tuple[bool, list[str]]` of English prose that
callers had to string-match. It now returns a `CapacityAssessment` reporting **six concepts
separately and never conflated**: physical fit, baseline fit, reserve required, total-capacity
exceedance, data sufficiency, human-review requirement — the first three tri-state, where `None`
means *unanswerable*, which is not the same as "no". A load that fits but consumes reserve is no
longer reported as a physical failure. Reserve impact is per dimension (weight, linear feet,
volume, pallets, drive/duty/cycle hours, flexibility buffer) with requested / raw remaining /
reserved / baseline available / consumed / remaining-after / over-capacity. `remaining_*` is signed
so **the real overage survives**; `display_remaining_*` clamps for the screen. Appointment
timestamps are parsed timezone-aware, and a naive timestamp is **refused as ambiguous rather than
assumed UTC**. `apply_asset_profile` mutates specs in place so live utilization is not erased.
Findings are structured: code, dimension, severity, message, source reference, human-review flag.

**B — Opportunity.** The second state list, the second transition table, `transition_to()`, the
stored `stage` and construction-time validation are gone. `stage` is a read-through property of the
correlated Spine work item, and an uncorrelated card answers `UNCORRELATED` rather than defaulting
to a stage. Analysis requests transitions; **Spine refuses illegal ones and Opportunity does not
swallow the refusal**. `Filtered` is a query — calling it twice with different thresholds gives two
answers and moves nothing. `Calendar Event` is gone from the lifecycle entirely. Commitment
requires a named human, refuses reserved system identities, records an `ApprovalEvent`, and
**creates nothing**: `dispatch/spine/commitment.py::realize` makes the load, and only against an
approval that names a real person.

**C — Security.** `check_secrets()` refuses to build an app on a published default outside
development mode. Development mode is explicit, warns loudly, and `development_host()` pins the
bind to loopback — the mode restricts behaviour, not just log output. Session cookie policy set.
Ignore rules extended for logs, keys, `.env*`, build artifacts.

**E — Tokens.** `dispatch/tokens.py` issues, verifies, revokes and audits. Signature is checked
before payload and payload before database, so a forged token cannot probe which object ids exist.
A correctly-signed token with no ledger row **fails closed** — it cannot be checked for revocation,
so it is not trusted on its signature alone. Legacy digests are **rejected by default**; an
operator with live links can open an expiring, audited grace window.

**F — CSRF.** `portal/csrf.py` binds a token to the session. Exemptions are exactly the login
gate's three, and a test asserts the list has not widened. Thirty-five `fetch()` call sites are
covered by one wrapper in `base.html` rather than thirty-five edits; nine HTML forms carry a hidden
field.

## 7. New capability built

| File | Lines | What |
|---|---|---|
| `dispatch/backup.py` | 926 | Backup/verify/restore engine |
| `scripts/dispatch_backup.py` | 119 | CLI: `backup` / `verify` / `restore`, `--dry-run`, `--force`, `--compress` |
| `BACKUP_AND_RECOVERY.md` | 201 | Operator procedure, exit codes, quarterly drill |
| `dispatch/tokens.py` | 372 | Token lifecycle with revocation and audit |
| `portal/csrf.py` | 128 | CSRF protection |
| `dispatch/spine/commitment.py` | 121 | The Spine side of the Opportunity boundary |

## 8. Files changed

**Application (13 modified, 5 added)** — `dispatch/capacity.py` (+1,727), `dispatch/opportunities.py`
(+356/−), `dispatch/truck_arrangement.py` (+342), `dispatch/notifications.py` (+94),
`portal/config.py` (+95), `cin_lite/email_delivery.py` (+76), `dispatch/db.py` (token schema wiring),
`portal/app.py`, `portal/routes/dispatch_api.py`, five templates, `.gitignore`. Added:
`dispatch/backup.py`, `dispatch/tokens.py`, `dispatch/spine/commitment.py`, `portal/csrf.py`,
`scripts/dispatch_backup.py`.

**Tests (5 modified, 7 added)** — added `test_dynamic_capacity.py` (54), `test_backup_restore.py`
(38), `test_token_lifecycle.py` (34), `test_opportunity_alignment.py` (32), `test_csrf_protection.py`
(23), `test_security_hardening.py` (18), `test_end_to_end_operating_path.py` (2). Modified
`conftest.py`, `test_architecture_discoveries.py`, `test_email_control.py`, `test_hardening.py`,
`test_archive_reference_wiring.py`, `test_stakeholder_evidence_download.py`.

## 9. Database and schema changes

Two tables, both additive, both created through the established per-subsystem initializer pattern
alongside the Spine's, in `dispatch/db.py::_init_db`:

- **`operational_tokens`** — token_id, purpose, object_id, issued_at, issued_by, expires_at,
  revoked_at, revoked_by, revoke_reason, plus an index on (purpose, object_id).
- **`token_audit`** — audit_id, token_id, purpose, object_id, event, reason, actor, at.

**No existing table was altered.** `loads.status` is untouched, per the narrow CF-04 reading.

## 10. Security changes

Refusal to start on a published secret · development mode that restricts the bind · session cookie
`HttpOnly`/`SameSite`/`Secure`/lifetime · CSRF on every mutating route · token expiry, scoping,
revocation and audit · legacy tokens rejected by default · upload allowlist, size cap, regenerated
filenames and checksum re-asserted by test · secrets excluded from backups by name pattern and
proven absent from every byte of the archive · ignore rules for logs and keys.

## 11. Test evidence

```
Command   python3 -m pytest -p no:cacheprovider
Result    3087 passed in 390.23s (0:06:30)
Exit      0
```

| Metric | Value |
|---|---|
| Baseline (start of campaign) | **2,882** |
| Final | **3,087** |
| Added | **+205** |
| Removed | **0** |
| Weakened | **0** |
| Failed | **0** |
| Skipped | **0** |
| Warnings | **0** |
| Errors | **0** |

**Three tests were rewritten, each to a stronger assertion.** Recorded here rather than buried:

1. `test_email_control.py::test_make_token_deterministic` asserted `t1 == t2` and a 64-character
   digest. **Determinism was inseparable from the defect** — a token containing only contract and
   action has nothing to expire on. Replaced by four tests: both tokens verify, an expired token is
   refused, a legacy digest is refused by default, and a legacy digest is accepted **only** inside
   an explicit grace window.
2. `test_stakeholder_evidence_download.py` and `test_archive_reference_wiring.py` compared a
   separately-minted token against the rendered page. With nonces that proves nothing. Both now
   extract the token the page **actually rendered** and assert it verifies — which the old
   assertions never did.
3. `test_hardening.py::test_using_default_secret_true` relied on no secret being configured.
   `conftest.py` now supplies real ones so the refusal path runs for real in all 87 `create_app()`
   call sites; the test arranges the unset case deliberately.

**On the campaign's explicit warning — "do not declare completion while most HTTP tests bypass the
security gates being claimed as protected":** CSRF is **not** disabled under `TESTING`. A
`CSRFTestClient` in `conftest.py` carries a real token, so all ~1,160 HTTP tests exercise the
protected path. `tests/test_csrf_protection.py` passes `csrf=False` to send raw, unprotected
requests exactly as a forged one would, and asserts they are refused. Likewise the secrets: the
suite supplies real values rather than being exempted from the check.

## 12. Coverage result

```
Command  python3 -m pytest --cov=cin_lite --cov=dispatch --cov=portal \
                           --cov-config=.coveragerc --cov-fail-under=90
Result   Required test coverage of 90.0% reached. Total coverage: 93.73%
```

CI measures `cin_lite`, `dispatch` and `portal` — widened in Wave 1 from `cin_lite` alone, which
had been measuring 14 % of production. **93.73 % against the 90 % gate**, with roughly 3,300 lines
of new application code added by this campaign. Coverage went in slightly (93.77 % → 93.73 %)
because `dispatch/backup.py`'s error branches and `dispatch/capacity.py`'s rarer finding paths are
not all exercised; the gate holds with margin.

## 13. Known remaining gaps

| Gap | Status |
|---|---|
| Outlook integration | **Not present, deliberately.** Outlook remains the scheduling source of truth by staying outside Dispatch. Doing nothing here is the correct behaviour. |
| Scheduler | Does not exist. Capacity's time evaluation is the advisory input a scheduler would consume. The campaign's required path names "Scheduler fit evaluated"; what is proven is the **capacity and time fit** that stands in for it. |
| ELD / GPS / weather / traffic / load boards | Not present. Nothing claims otherwise, and `set_verified_hos` now refuses to pretend an ELD supplied a reading. |
| Archive Review Queue decision route | Model recovered in Wave 1; the route still needs rewriting against `main`'s identity layer rather than the excluded security stack. |
| `REVIEW_AGE_DAYS = 180` | Still a stand-in, not doctrine — Archive records have no version history, so the policy's literal trigger remains unimplementable. |
| 17 cross-repository citations | Untouched; belongs with the governance-home decision. |
| C1 duplicate sandbox status, C2a `/calendar`, C4 replay guards | Open corrective missions, not in this campaign's scope. |
| Point-in-time backup consistency | Backups are **cold-consistent**, not a synchronized snapshot across all four stores. Documented in `BACKUP_AND_RECOVERY.md`; fixing it needs a quiesce or filesystem snapshot. |
| Backup encryption | Not implemented; documented as a media-level concern. |

## 14. Blocked units

**None.** Every unit in the authorized package was implemented.

## 15. Mike-only decisions still open

1. **`loads.status` scope under CF-04** — the narrow reading was applied as instructed. Whether Spine
   should ever absorb it remains open, and gates nothing currently scheduled.
2. **Governance home (CF-01)** — five families across six repositories.
3. **`DF-` clause prefix (CF-02)** — D11/D12/D13 collide between two live registers.
4. **BM-02 and the Manager (CF-05)** — 866 lines + 790 test lines exist, wired, on a branch.
5. **`REVIEW_AGE_DAYS`**, or approving Archive version history.
6. **The 402 protected conflict notices** — untouched, as required.
7. **Legacy token grace window** — whether any live stakeholder or decision link needs
   `DISPATCH_LEGACY_TOKENS_UNTIL` set before this deploys. **If none were ever issued, set nothing.**

## 16. Rollback instructions

Every workstream is additive or self-contained. To roll back the whole campaign:

```
git revert <campaign commit>          # one commit, this branch
```

Partial rollback, by workstream:

| Workstream | Revert |
|---|---|
| F (CSRF) | Remove `init_csrf(app)` from `portal/app.py`. The module and templates become inert. |
| E (tokens) | `dispatch/notifications.py` and `cin_lite/email_delivery.py` only. **Existing v2 tokens stop verifying** — revoke and reissue. Tables can stay; nothing else reads them. |
| C (secrets) | Set `DISPATCH_MODE=development`, or revert `portal/config.py::check_secrets`. |
| D (backup) | Delete `dispatch/backup.py`, `scripts/`, its test and doc. Nothing imports them. |
| B (Opportunity) | Revert `dispatch/opportunities.py` and delete `dispatch/spine/commitment.py`. **This reinstates a competing lifecycle authority** — it is a doctrine reversal, not just a code one. |
| A (capacity) | Revert `dispatch/capacity.py` and `dispatch/truck_arrangement.py`. **This reinstates `verified_by="Mike Zachary"`.** |

Schema: the two new tables are additive and harmless if left. No migration to reverse.

## 17. Operational walkthrough

```
1.  Set PORTAL_SECRET_KEY and DISPATCH_EMAIL_SECRET.       Without them the app refuses to start.
2.  python portal/app.py                                    Fails closed to /login.
3.  Intelligence ingests opportunities.                     Each gets a Spine work item, state CREATED.
4.  Analysis consults Dynamic Capacity.                      Consumption %, deadhead, fuel, projected
                                                             profit. Unknowns stay unknown.
5.  Scoring ranks them.                                      Score reduces noise. It does not decide.
6.  present() puts the shortlist up.                         Spine walks to WAITING_FOR_MIKE.
7.  Mike commits, by name.                                   ApprovalEvent recorded. A system identity
                                                             is refused.
8.  Spine realises the commitment.                           The load and the rate are created on the
                                                             Spine side, against that approval.
9.  Driver is assigned and logs in.                          Phone + PIN, own session namespace.
10. Driver reports milestones and POD.                       CSRF enforced; refusals are shown, never
                                                             silent; evidence is checksummed.
11. Stakeholder link is issued.                              Scoped, expiring, revocable, audited.
12. scripts/dispatch_backup.py backup /path                  Manifest + sha256 for every file.
13. scripts/dispatch_backup.py restore <archive> <dest>      Refuses a non-empty destination.
```

## 18. Production claims now proven

Each of these is asserted by a behavioural test that fails if the claim stops being true.

- A deployment **cannot start** on a published default secret outside development mode.
- Development mode **cannot bind** anything but loopback while running on published secrets.
- Every mutating route **refuses** a missing, invalid or cross-session CSRF token, and the store is
  unchanged when it does.
- A stakeholder token **expires**, and **can be revoked** individually or per load, and the live HTTP
  route honours both.
- A revoked token **cannot download evidence**.
- A legacy token is **refused by default**.
- Operational data **survives total loss**: the estate is deleted and the load, the milestone and the
  POD bytes come back out of the backup, verified by hash.
- Secrets are **absent from every byte** of a backup archive.
- Opportunity **cannot** create a load, confirm a rate, or move its own lifecycle.
- A commitment **cannot** be realised without a human approval naming a real person.
- Capacity **cannot** report a stale configuration as feasible, and **cannot** claim a verification
  nobody made.
- A driver **is told** when a transition is refused, a file is rejected, or a field is invalid.
- A fuel receipt **cannot** be anonymous: driver, truck, timestamp, jurisdiction and receipt evidence
  are all required, and no artificial load association is created.

## 19. Still simulated, estimated or unverified

Stated plainly, because the campaign's objective is a Dispatch that tells the truth.

| Item | Status |
|---|---|
| **The `D:` delivery path** | **UNVERIFIED.** `bootstrap_d_drive.py` has still never run against a real Windows volume. Backup and restore are proven on POSIX and honour the `D:` root variables, but no session has written to that drive. Only Mike can close this. |
| **HOS readings** | **ESTIMATED or UNKNOWN by construction.** No ELD exists. `set_verified_hos` now requires an explicit source and refuses to imply one. |
| **Route Risk feeds** | **SIMULATED.** Every event carries `is_live_data: False`. No weather, traffic or DOT integration exists. |
| **Fuel cost and drive-hour estimates** | **ESTIMATED** — $3.80/gal at 6.5 mpg, 50 mph average. Constants, not measurements. |
| **Scheduler fit** | **NOT IMPLEMENTED.** Capacity's time evaluation is advisory input; there is no scheduler and Outlook remains the schedule. |
| **Map visuals** | **PLACEHOLDER.** |
| **Load board acquisition** | **SAMPLE DATA** unless `DISPATCH_LOAD_SOURCE` is configured. |
| **Backup point-in-time consistency** | **COLD-CONSISTENT**, not synchronized across stores. |
| **cin_lite token revocation** | **BY CONSUMPTION**, not a ledger. A decision resolves once; the second attempt is refused regardless of token quality. cin_lite is standalone by design and has no database to hold a revocation ledger. |
