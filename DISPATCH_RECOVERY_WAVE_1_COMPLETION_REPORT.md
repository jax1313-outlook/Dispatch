# DISPATCH_RECOVERY_WAVE_1 — COMPLETION REPORT

**Authorized package:** the fuel-receipt ownership decision, plus recovery units **R-01 … R-04**
from `DISPATCH_RECOVERABLE_WORK_MATRIX.md`.
**Result: COMPLETE**, with one unit reported **BLOCKED** rather than forced — see §4.
**Full suite: 2,882 passed, exit 0** (baseline at the start of this package: 2,817).

---

## 1. Completion report

| Unit | Work | Status | Tests |
|---|---|---|---|
| **Fuel ownership** | Rework to Mike's ownership chain | ✅ Done | 30 (driver file, from 6 on the branch) |
| **R-01** | Driver Transformation recovery + 5 repairs | ✅ Done (commit `da9f3dc`) | — |
| **R-02a** | CI coverage gate widened | ✅ Done | measured **93.77 %** |
| **R-02b** | `dispatch/spine/` recovered and wired | ✅ Done | +23 |
| **R-02c** | Archive Review Queue model | ✅ Done | +11 |
| **R-02d** | Portal card levels / Version Doctrine | ⛔ **BLOCKED** — §4 | — |
| **R-02e** | `dispatch/security/`, `dispatch/manager/` | ⊘ Excluded by CF-03 / BM-02 | — |
| **R-03** | Route Risk ordering tie-break | ✅ Done | +1 |
| **R-04** | `PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` + citations | ✅ Done | — |

**Net: +65 tests, 0 removed, 0 weakened.**

## 2. Resolved findings

### F-1 · Fuel receipts were unowned — **resolved to Mike's chain**

Mike's ruling, verbatim: *"Fuel receipt ownership shall remain scoped. Fuel receipts shall never be
anonymous."* All five links are now mandatory, and a receipt that cannot supply all five is refused
rather than filed thin:

| Link | Enforcement |
|---|---|
| **Driver Identity** | From the session; re-resolved against the driver record on every post |
| **Truck Identity** | `equipment_id` required, must name **active** fleet equipment; stored in `vehicle_id` |
| **Timestamp** | Recorded explicitly, not left to a default |
| **Jurisdiction** | Required, validated against all 64 IFTA jurisdictions |
| **Receipt Evidence** | **The photo is required.** Attached through `attach_ifta_fuel_evidence()` with a checksum |

**My earlier reading was too strict, and Mike corrected it.** I had required an *active load*.
The ruling: *"Association with an active load is preferred but not required… Owner/Operator
workflows must support reporting fuel receipts when no active load exists."* That is now the
behaviour — the scanner is offered whenever an active truck exists, a load rides along only when
there is one, and **no artificial load association is ever created**. `test_logged_without_a_load_and_no_load_is_invented`
asserts the absence.

One design consequence worth naming: because the ownership chain requires evidence, a purchase must
never exist without its receipt. The receipt is therefore **validated before any record is written**,
and if the attach still fails the purchase is deleted rather than left standing. A fuel row with no
receipt is exactly what "never anonymous" forbids.

### F-2 · Two silent-failure defects and three crash paths — resolved (R-01, commit `da9f3dc`)

Detailed in `DRIVER_TRANSFORMATION_RECOVERY_WALKTHROUGH_REPORT_v1.md`.

### F-3 · CI measured 14 % of production — resolved

`--cov=cin_lite --cov=dispatch --cov=portal`. **The threshold did not need lowering:** measured
coverage of the widened scope is **93.77 %**, already above the existing 90 % gate. The gate was
never too strict; it was pointed at one seventh of the program.

### F-4 · The Spine is recovered and wired

835 lines, 25 states, a 25-key transition table, six tables, initialised from `_init_db`. **23 tests
pass against today's `main`.** Five hand-written lines, exactly as measured in the Wave 1 report.

Per **CF-04**, Spine is now the authoritative lifecycle engine. It lands as an available capability;
**`dispatch/opportunities.py` is untouched and still unwired**, and its alignment (OPP-01…OPP-09) was
not authorized and was not started.

The branch's `_init_db` hunk also imported `dispatch.security.db`. **The hunk was split** and the
security half dropped — CF-03: main's PIN gate supersedes that stack.

### F-5 · Route Risk "latest" was non-deterministic — resolved

`ORDER BY created_at DESC` → `ORDER BY created_at DESC, rowid DESC`. `created_at` is second
precision, so two conditions in the same second had no defined order, and `get_route_risk()` takes
the first row as "the latest" — meaning **which condition a driver saw could flip between runs**.
The branch's own test targeted a `_StubRouteRisk` adapter this module does not have; a new test was
written against the real post-M3 design, forcing both rows to share a timestamp via direct SQL and
asserting the deterministic winner.

### F-6 · A document cited ten times existed nowhere — resolved

`governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`, 177 lines, recovered from the Jules
repo. All citations in `portal/models/identity.py`, `portal/app.py`, `portal/routes/auth.py` and
`tests/test_portal.py` now point at the path in this repository instead of *"(Claude-3 repo)"*,
which was the wrong repository.

### F-7 · Two regressions caught while recovering — **the important ones**

Both would have shipped silently under a file-level recovery:

- **`portal/models/archive.py`** — the branch version is from an older base. Taking the file whole
  **dropped 58 lines of main's work**: `ArchiveApprovalError`, `RESERVED_SYSTEM_IDENTITIES`, the
  `intelligence` archive section, and `archive_from_intelligence()`. It also replaced
  `atomic_write_json()` with a bare `path.write_text()` — **regressing M-A**. Reverted to main and
  the Review Queue re-applied as a patch. Main's governance gate and atomic writes are intact, and
  `tests/test_atomic_store_writes.py` still passes.
- **The same `write_text` regression** exists in the branch's `portal/models/conflict.py`, which is
  one of R-02d's files. It is part of why R-02d is blocked.

This is what proposed constraint **BM-17** ("recovery is cherry-pick, not merge") is for, at file
granularity as well as commit granularity.

## 3. Unresolved findings

| # | Finding | Disposition |
|---|---|---|
| U-1 | **The Archive Review Queue's decision route was not recovered.** Nine of the branch's 21 tests exercise `POST /api/archive/review-decision`, which depends on `dispatch/security/`'s `@authority_required`, `get_current_session()` and `get_current_user()`. | Excluded per CF-03. The route should be **rewritten** against main's identity layer — `ApprovalEvent.session_id` and `.role` are optional, and `get_authority_user_id()` supplies `user_id`. Its own unit; a note in the test file records exactly what was left and why. |
| U-2 | **`REVIEW_AGE_DAYS = 180` is not doctrine.** `ARCHIVE_REVIEW_POLICY.md`'s literal *"Current + 3 Previous"* trigger **cannot be implemented** — `create_record()` silently no-ops on a repeat `source_id`, so Archive records have no version history to count. | Recovered with the number and an explicit docstring saying it is a stand-in. **Mike sets it, or approves version history for Archive records.** Wave 1 decision 3. |
| U-3 | **17 further cross-repository citations** were found while fixing R-04's ten — `portal/models/publisher.py`, `library.py`, `intelligence.py`, `archive.py`, `helpers.py`, `routes/api.py`, `reconciliation/__init__.py` and `tests/test_portal.py` all cite Claude-3 documents by name. | Out of R-04's scope. Belongs with **CF-01 / OWN-02** (governance home). None was touched. |
| U-4 | **`loads.status` scope under CF-04** — does "single source of lifecycle truth" absorb it? | Referred to Mike. Blocks only OPP-04. Reading A (narrow) recommended. |
| U-5 | **CSRF (W2-5) and session expiry (W2-3) remain open** across all 109 mutating routes, the four driver endpoints included. | Not authorized; not started. Recorded rather than assumed away. |
| U-6 | **Three state machines now exist in the repository** — `loads.status` (live), `dispatch/spine/` (recovered, wired, available), `dispatch/opportunities.py` (unwired, superseded by ruling). | Expected and temporary. CF-04 settles which is authoritative; OPP-01…OPP-06 remove the third. **Nothing consumes `opportunities.py`**, so no runtime ambiguity exists today. |

## 4. Dependencies encountered

| Dependency | Effect |
|---|---|
| **R-02c → R-02b** | The Archive Review Queue's test file imports `dispatch.spine.store` at module level. Landing the model alone gives **the code with none of its tests**. Spine was recovered first. |
| **R-02c → CF-03** | Its decision route needs the excluded security stack. Split: model recovered, route deferred (U-1). |
| **R-02b → CF-04** | Recovering the Spine was gated on the lifecycle adjudication. Mike's ruling supplied it. |
| **R-02b → CF-03** | The branch's `_init_db` hunk imports both `spine.db` and `security.db`. Split; security half dropped. |
| **R-03 → new test** | The branch's test targets an implementation main does not have. Recovered the fix, wrote the test. |
| **R-02d → BLOCKED** | Two verified blockers, neither worth forcing: (1) the branch's `portal/models/conflict.py` uses `path.write_text` and would **regress M-A's atomic writes**, which a structural test forbids; (2) its `portal/models/sandbox.py` is a different, 213-line-larger implementation that **collides with the open C1 corrective mission** on the duplicate `engine_status`. **Recommendation: recover R-02d after C1 closes**, as a patch, never as a file copy. |

## 5. Files changed

**Application code (7)**
`dispatch/db.py` (Spine schema wiring, +9) · `dispatch/store.py` (route-risk tie-break, +8) ·
`dispatch/spine/` (5 new files, 835 lines) · `portal/models/archive.py` (Review Queue patch, +81) ·
`portal/routes/driver_portal.py` (fuel ownership chain) · `portal/templates/driver_home.html`
(truck selector, load-optional card) · `portal/app.py`, `portal/models/identity.py`,
`portal/routes/auth.py` (citation paths only)

**Tests (5)**
`tests/test_driver_portal.py` (30) · `tests/test_spine.py` (23, new) ·
`tests/test_archive_review_queue.py` (11, new, trimmed to the recovered model) ·
`tests/test_route_risk_durability.py` (21, +1) · `tests/test_portal.py` (citation only)

**Configuration and governance (4)**
`.github/workflows/ci.yml` · `governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` (new, 177) ·
`DECISION_LOG.md` · this report

## 6. Recommendations

1. **Rewrite the archive decision route** against main's identity layer (U-1). It is the only piece of
   R-02c left, and it does not need the security stack.
2. **Set `REVIEW_AGE_DAYS`** (U-2) — or approve Archive version history, which is the real fix and
   makes `ARCHIVE_REVIEW_POLICY.md`'s own trigger implementable.
3. **Close C1, then recover R-02d as a patch.** Both blockers dissolve in that order, and neither
   dissolves in the other.
4. **Authorize OPP-01…OPP-06.** The Spine is in and Mike's ruling is recorded; `opportunities.py`'s
   stage machine is now superseded doctrine sitting in the tree. Answering U-4 unblocks OPP-04, but
   the other five do not wait on it.
5. **Schedule W2-5 (CSRF).** It is the largest open security item and a stop-the-world mission —
   every new write surface, including the four driver endpoints, increases what it has to cover.
6. **Fold the 17 remaining cross-repository citations into OWN-02** (U-3) rather than fixing them
   piecemeal.
