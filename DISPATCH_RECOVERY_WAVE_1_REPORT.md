# DISPATCH_RECOVERY_WAVE_1_REPORT

**Recovery requirements for the three Wave 1 candidates.**
**Authorization:** *"You are authorized to proceed with: 1. Portal adjudication recording
2. Packaging repair (Path B) 3. Recovery Wave 1 planning. Do not begin broad repairs yet."*
**Status: PLANNING ONLY.** No recovery was performed. Every measurement below comes from a
**throwaway worktree at `origin/main` @ `37f4fd0`**, which was destroyed afterwards. The repository
carries three changed files from this session — `pyproject.toml`, `.gitignore`, `DECISION_LOG.md` —
and no recovered code.

---

## 0. Method — measured, not estimated

Each candidate was actually landed on today's `main` in a detached worktree, wired, and run. Numbers
below are observed test results, not projections. The worktree was reset with `git reset --hard`
between trials — an earlier trial was invalidated by a dirty index and re-run rather than reported.

| Trial | What was landed | Result |
|---|---|---|
| 1 · Spine | `dispatch/spine/` + `tests/test_spine.py` + a split `db.py` hunk | **2,840 passed, exit 0** |
| 2 · Driver Transformation | 3 files from `afd6e00` | **2,823 passed, exit 0** |
| 3 · Archive Review Queue | `portal/models/archive.py` + tests, then + spine | **12 of 21 pass; 9 blocked** |

Baseline for comparison: `main` alone is **2,817 passed, exit 0**.

---

## 1 · SPINE — `dispatch/spine/`

### Current state

| | |
|---|---|
| Source | `origin/stage13-testing-hold-review` (chain tip, `0e2096a`), authored 2026-08-10 |
| Size | **835 lines** across 5 files, plus `tests/test_spine.py` (295 lines, **23 tests**) |
| On `main` | **Absent.** `grep -rn "spine" --include=*.py` on `main` → 0 matches |
| Model | `state.py` — **25 states, 25-key transition table**, matching Spine Specification §6 |
| Schema | `db.py` — 6 tables: `work_items`, `events`, `portal_cards`, `audit_events`, `approval_events`, `conflict_events` |
| Wiring on the branch | `dispatch/db.py::_init_db` calls `init_spine_schema(conn)`; `portal/routes/api.py` consumes `WorkItem`, `ApprovalEvent`, `AuditEvent`, `create_work_item`, `create_approval_event` |

### Defects

**None found.** This is the cleanest of the three. The package has no dependency on
`dispatch/security/`, no dependency on `portal/`, and its 23 tests pass unmodified against today's
`main`.

One design note, not a defect: it is a **second persistence root** — its own `init_spine_schema`
alongside `_SCHEMA`'s 26 tables, in the same database file. That is deliberate and consistent, but
it is the thing CF-04 is about.

### Recovery effort — **LOW. Measured.**

| Step | Work |
|---|---|
| Copy 5 files + 1 test file | `git checkout <branch> -- dispatch/spine tests/test_spine.py` |
| Wire the schema | **5 lines** in `dispatch/db.py::_init_db` |
| Total edit | **5 lines written by hand.** Everything else is a file copy. |

**Verified result: 2,840 passed, exit 0** — the 2,817 baseline plus exactly its own 23, with no
regression anywhere.

### Merge blockers

**One, and it is small.** The branch's `db.py` hunk imports **both** `spine.db` and `security.db`:

```python
from dispatch.spine.db import init_spine_schema
from dispatch.security.db import init_security_schema
init_spine_schema(conn)
init_security_schema(conn)
```

`dispatch/security/` is excluded (CF-03 — `main`'s PIN gate supersedes it). **The hunk must be
split**, taking the spine half only. That was done in the trial and works.

Not a blocker, but note: the branch's `portal/routes/api.py` spine consumer is the *Archive Review
Queue decision route*, which is candidate 3 — so the Spine can be recovered with **no `portal/`
change at all**. It lands as an available, tested, unconsumed capability.

### Doctrine conflicts

**CF-04, and it is the whole question.** BM-10: *"No mission may merge the load-status and work-item
state models, replace either, or create a third state authority."*

- `dispatch/spine/` **is** the work-item model BM-10 protects. Recovering it is compliant.
- `dispatch/opportunities.py` on `main` **is** a third model, and BM-10 forbids it.

Recovering the Spine while `opportunities.py` sits unadjudicated would give Dispatch **three** state
machines in one repository. **These are one decision, not two.** BM-18 (proposed) also applies: no
module is connected before its model is adjudicated.

**Recommendation:** approve the Spine and dispose of `opportunities.py` in the same instruction.

---

## 2 · DRIVER TRANSFORMATION — Missions 1–4

### Current state

| | |
|---|---|
| Source | `origin/jules-driver-transformation-missions-1-4-…`, commit `afd6e00`, 2026-08-22 |
| Genuinely new files | **3** — `portal/routes/driver_portal.py` (+166), `portal/templates/driver_home.html` (+235), `tests/test_driver_portal.py` (144 lines, **6 tests**) |
| Fourth file | `portal/routes/dispatch_api.py` (+18) — **already on `main`.** The 409 `status_transition_refused` response landed with PR #111. The branch's version is a duplicate. |
| Rest of the branch | A full re-implementation of PR #111 (M1, M3, M-A, C3, all walkthrough reports, `DECISION_LOG.md`). **Already on `main`. Must be discarded, not merged.** |
| New endpoints | `POST /driver/loads/<id>/milestone` · `POST /driver/loads/<id>/pod` · `POST /driver/loads/<id>/exception` · `POST /driver/fuel-receipt` |

### Defects — **four, all confirmed by reading the source**

| # | Severity | Defect |
|---|---|---|
| **D-1** | **High** | `driver_step_milestone` wraps `add_milestone()` in `except Exception: pass`. When the M1 gate refuses the transition, the driver is redirected as though it worked. **`flash` is imported and never used.** Fails the 70 MPH test outright: a driver at a dock cannot tell whether the tap registered. |
| **D-2** | Medium | Same `except Exception: pass` in `driver_log_exception`. |
| **D-3** | **High** | `driver_fuel_receipt` has **no `_verify_driver_load()` and no load association** — the only write endpoint on the branch with no scoping. Any authenticated driver can write arbitrary rows into the company IFTA fuel ledger. **IFTA is a tax filing.** |
| **D-4** | Low | `float(gallons_val)` / `float(amount_val)` unguarded — a non-numeric form value returns 500. |

**Test coverage is thin against exactly these defects.** Six tests for four write endpoints, and
none asserts a *refused* transition or fuel-receipt scoping. The tests prove the happy paths work;
they do not prove the failure paths behave.

### What is genuinely good, recorded so the defects do not obscure it

Writes go **through** `services.add_milestone()` and `attach_evidence()`, not around them — so the
M1 transition gate, the C3 audit trail, the extension allowlist, the 25 MB cap and the SHA-256
checksum all apply unchanged. `_verify_driver_load()` is a real IDOR check on the three load-scoped
routes. This is the correct shape; it is four fixes from being correct behaviour.

### Recovery effort — **LOW to land, MEDIUM to make safe**

| Step | Work |
|---|---|
| Land 3 files | File copy. **Verified: 2,823 passed, exit 0.** Zero conflicts against `main`. |
| Fix D-1, D-2 | Catch `ValueError` specifically, `flash()` the refusal reason, render it on the cockpit. ~15 lines + template. |
| Fix D-3 | Scope the fuel receipt to a driver's own load, or move it off the driver surface. **Design decision, not just code.** |
| Fix D-4 | Guarded parse. ~4 lines. |
| New tests | A refused transition must show the driver something; a driver must not write an unscoped IFTA row. ~4–6 tests. |

### Merge blockers

**None technical.** Three files, no conflicts, suite green.

**One procedural, and it matters:** the commit must **not** be cherry-picked whole. It re-adds the
entirety of PR #111. Recover by path (`git checkout <branch> -- <3 paths>`), never by commit —
proposed constraint **BM-17**.

### Doctrine conflicts

**None. It is the doctrine.** Driver-First §0 and the 70 MPH test are what this implements; the
baseline audit named the absent driver write surface as the program's largest gap.

**But D-1 inverts the doctrine it serves.** A control that silently swallows a refusal is worse for
a driver than no control — he taps, nothing visible happens, and he has no idea whether Dispatch
recorded anything. **Fix before landing, not after.**

---

## 3 · ARCHIVE REVIEW QUEUE

### Current state

| | |
|---|---|
| Source | `origin/stage6-archive-review-queue` (`9a9889b`), also in the `stage13` chain |
| Footprint | `portal/models/archive.py` (+75) · `portal/routes/api.py` (+79) · `portal/routes/pages.py` (+4) · `portal/templates/archive.html` (+34) · `portal/templates/base.html` (+12) · `tests/test_archive_review_queue.py` (259 lines, **21 tests**) |
| On `main` | **Absent.** The `retention` table exists; nothing can review or dispose of a record. |
| What it does | Age-based review queue (`REVIEW_AGE_DAYS = 180`), `review_status` of `pending`/`kept`/`deleted`, `list_review_queue()`, `mark_reviewed()` — and **"deleted" records a disposition, never a physical removal**, per `ARCHIVE_REVIEW_POLICY.md` §6 |

### Defects

**None found in the model.** It is careful work: records predating the field default to `pending` via
`.get()` so nothing is silently excluded; a second decision on the same record is refused rather than
allowed to overwrite the first, matching `IFTAReportApproval`'s existing convention.

Its own docstring discloses a real limitation honestly: the age trigger is a stand-in because
`ARCHIVE_REVIEW_POLICY.md`'s literal *"Current + 3 Previous"* rule **cannot be implemented** —
`create_record()` silently no-ops on a repeat `source_id`, so Archive records have no version
history to count. That is a doctrine-versus-reality gap this candidate surfaces rather than papers
over, and it should reach Mike.

### Recovery effort — **splits into three, with sharply different costs**

| Piece | Contents | Dependencies | Effort | Measured |
|---|---|---|---|---|
| **3a · Model** | `portal/models/archive.py` +75 | **None** | **LOW** | Imports and works against `main` unmodified |
| **3b · Model + Spine** | 3a + `dispatch/spine/` | Candidate 1 | LOW | **12 of 21 tests pass** |
| **3c · Decision route + page** | `api.py` +79, `pages.py` +4, 2 templates | Spine **and** `dispatch/security/` | **HIGH** | **3 failed, 6 errors** — 9 tests blocked |

### Merge blockers — **this is the important finding**

**The test file cannot load without the Spine.** `tests/test_archive_review_queue.py:13` does
`from dispatch.spine.store import list_approval_events` at module level. Landing the model alone
gives you **the code with none of its tests**:

```
ModuleNotFoundError: No module named 'dispatch.spine'
Interrupted: 1 error during collection
```

**The decision route needs the excluded security stack.** `api.py`'s `archive_review_decision` uses
`@authority_required`, `get_current_session()` and `get_current_user()` from `portal/auth_helpers.py`,
which reads `dispatch/security/`. Line 150 of the test file imports `dispatch.security.auth` directly.
CF-03 excludes that stack — `main`'s fail-closed PIN gate supersedes it and is newer.

**A path exists, and it is not "recover security".** `ApprovalEvent`'s `session_id` and `role` are
both `str | None = None` — optional. `main`'s `portal/models/identity.py` supplies
`get_authority_user_id()` and `record_session_created()`, which is enough to populate `user_id`.
The route can be **rewritten** against `main`'s single-Authority session model, leaving `session_id`
and `role` null. That is a real, honest gap to record — `main` has no role concept and no session id
— but it is a rewrite of one route, not the adoption of a second auth stack.

### Doctrine conflicts

| Conflict | Detail |
|---|---|
| **CF-03** | 3c depends on `dispatch/security/`, which is superseded. **Rewrite the route; do not recover the stack.** |
| **CF-04** | 3b and 3c depend on the Spine, so they inherit the state-model decision. |
| **Doctrine gap surfaced** | `ARCHIVE_REVIEW_POLICY.md`'s *"Current + 3 Previous"* trigger is unimplementable against today's Archive. `REVIEW_AGE_DAYS = 180` is a **tunable default standing in for doctrine, and is not doctrine.** Mike should either set the number deliberately or approve version history for Archive records (that was Stage 8). |
| Not a conflict | "Deleted" as a recorded disposition rather than a purge is exactly `ARCHIVE_REVIEW_POLICY.md` §6. |

---

## 4 · Wave 1 summary

| | Spine | Driver Transformation | Archive Review Queue |
|---|---|---|---|
| Lines recovered | 835 + 295 tests | 401 + 144 tests | 204 + 259 tests |
| Hand-written lines needed | **5** | ~25 + tests | ~90 (route rewrite) |
| Conflicts against `main` | **0** | **0** | 0 for the model |
| Suite result | **2,840 ✅** | **2,823 ✅** | **12/21** (needs Spine) |
| Defects | **none** | **4 (2 High)** | none in the model |
| Merge blockers | split one hunk | recover by path, not by commit | tests need Spine; route needs a rewrite |
| Doctrine gate | **CF-04** | none | CF-03, CF-04, plus a policy gap |
| Effort | **LOW** | LOW + MEDIUM repair | LOW / MEDIUM / HIGH by piece |

### Dependency order — forced by the evidence, not by preference

```
CF-04 decision  ──►  Spine  ──►  Archive Review Queue (3a+3b, tests now runnable)
                                        │
                                        └──►  3c route rewrite against main's identity layer

Driver Transformation  ──  independent of all of the above
                           (blocked only by its own 4 repairs, and by W2-3/W2-5)
```

**The Driver Transformation is the only one of the three that needs no adjudication.** It is also
the one that closes the program's largest gap. If exactly one thing proceeds after this report, it
is the driver repair — and the repair, not the recovery, is the work.

### What must NOT happen

- Do not recover the Spine while `opportunities.py` sits unadjudicated — that makes three state
  machines instead of resolving two.
- Do not cherry-pick `afd6e00` as a commit. Recover its three paths.
- Do not recover `dispatch/security/` to unblock the archive route. Rewrite the route.
- Do not land the Driver Transformation with `except Exception: pass` intact. A silent refusal on a
  driver's screen is worse than no button.

---

## 5 · Decisions this report puts in front of Mike

| # | Decision | Blocks |
|---|---|---|
| 1 | **CF-04** — recover `dispatch/spine/` as the work-item model **and** dispose of `opportunities.py`, as one instruction | Spine, Archive 3b/3c |
| 2 | Does the fuel-receipt scan belong on the driver surface at all, and if so scoped to what? | Driver D-3 |
| 3 | `REVIEW_AGE_DAYS` — accept 180, set a different number, or approve Archive version history first | Archive 3a |
| 4 | Approve rewriting `archive_review_decision` against `main`'s identity layer, accepting null `session_id`/`role` | Archive 3c |

**Nothing in Wave 1 proceeds without decision 1, except the Driver Transformation.**
