# STAGE13_TESTING_HOLD_REVIEW_WALKTHROUGH_REPORT_v1

## Testing and Hold Review — full regression + coverage-gate fix, no product code

**Status:** Implemented and verified. Branch: `stage13-testing-hold-review` (based on `stage12-manager-m7-policy-hook`, the confirmed full Stage 2–12 aggregate).

**Responds to:** Mike's "Approve Stage 13 build," followed by review and approval of `DISPATCH_STAGE13_TESTING_HOLD_REVIEW_BUILD_DESIGN_v1.md` ("Approve design").

---

## What This Is

Stage 13 certifies everything built in Stages 4–12 as one suite, and fixes a real gap the investigation found in the coverage gate itself. No Manager, Portal, Spine, or Security behavior changed. Two files touched, both test/CI infrastructure.

## What Changed

1. **`.github/workflows/ci.yml`** — the pytest invocation now passes `--cov=dispatch --cov=portal` alongside the pre-existing `--cov=cin_lite`. Previously it measured `cin_lite` only.
2. **`.coveragerc`** — `portal` added to `[run] source`, joining `cin_lite` and `dispatch`. Previously `portal` wasn't listed at all, so even a bare `pytest --cov` (no explicit `--cov=` flags) would have missed it too.

## What Did Not Change

No file under `dispatch/`, `portal/`, or `cin_lite/` itself was touched. No new tests were added — Stage 13's own scope explicitly excludes writing new tests to close the coverage gaps this review surfaced (see Risk Notes below and the design's Open Question 2).

## Automated Test Results

- **Full suite, unmodified command (pre-existing CI behavior):** 2,489 tests, 0 failures, 0 errors. Reported coverage: 96.77% — but that figure is `cin_lite` alone; `dispatch` and `portal` are silently absent from the report under the old command.
- **Full suite, corrected command (this stage's fix):** same 2,489 tests, 0 failures, 0 errors. Coverage now genuinely spans all three packages: **8,816 statements, 421 missed, 95.22% aggregate — clears the existing 90% `fail_under` gate correctly, for the first time measuring what it claims to measure.**
- Test count cross-checked via `pytest --collect-only -q` summed across all 84 test files: 2,489, matching exactly — confirms Stage 13 added zero tests and dropped none.
- `coverage.xml` generation (used by CI's artifact-upload step) confirmed working under the corrected command.

## §22 Test-Category Inventory (`DISPATCH_FINAL_BLUEPRINT_v1.md` §22)

| # | Category | Representative test file(s) | Status |
|---|---|---|---|
| 1 | State transition tests | `test_spine.py` | Exercised |
| 2 | Permission tests | `test_security_foundation.py` (role validity only — see #14/#15) | Partially exercised |
| 3 | PIN authentication tests | `test_security_foundation.py` | Exercised |
| 4 | Approval audit tests | `test_spine.py`, `test_archive_review_queue.py`, `test_ifta_report_approvals.py` | Exercised |
| 5 | Portal card tests | `test_manager_foundation.py`, `test_spine.py` | Exercised |
| 6 | Version display tests | `test_version_doctrine.py` | Exercised |
| 7 | Archive retention tests | `test_archive.py`, `test_archive_review_queue.py` | Partially exercised — age-based Review Queue is tested; the literal "current + 3 previous" version-retention rule remains blocked on Stage 8 (Version Doctrine on Archive), per Stage 6's own design |
| 8 | Library promotion tests | `test_portal.py`, `test_version_doctrine.py` | Partially exercised — `portal/models/library.py` is well-covered as a data model (97%), but no dedicated "no promotion without Approval Event" test file exists |
| 9 | Fact grounding tests | — | Not yet applicable — Publisher/Intelligence fact-grounded generation is not yet built to the depth §22 describes; current `publisher.py`/`intelligence.py` are data models |
| 10 | Publisher no-fabrication tests | — | Not yet applicable, same reason as #9 |
| 11 | Intelligence verification tests | — | Not yet applicable, same reason as #9 |
| 12 | Alert governance tests | — | Not yet applicable — Stage 10 was redefined as analysis-only; no permanent-suppression mechanism exists yet to test |
| 13 | Load evaluation tests | `test_scoring.py` | Partially exercised — Spine scoring is tested; full Intelligence-interpretation-through-Portal-presentation chain is not, consistent with #9–#11 |
| 14 | Driver portal boundary tests | — | Not yet built — confirmed by direct inspection: no test exercises the Driver role's boundary; the only "driver" hit in `test_portal.py` is a column label, not a boundary test |
| 15 | External viewer boundary tests | — | Not yet built — `External Viewer` is a defined role (`dispatch/security/models.py`) with no dedicated boundary test |
| 16 | No-autonomous-action tests | Distributed structural guards across `test_manager_foundation.py`, `test_archive_review_queue.py`, `test_security_foundation.py` | Exercised, but no single consolidated file — the property is checked per-module (source-scanning for forbidden write/approve/book calls) everywhere Manager or Archive code was built |

Categories #14 and #15 (Driver and External Viewer boundary tests) are the same gap Stage 7's launch package already named and deferred ("#4, #5 — retrofitting the three HMAC gates, broader page enforcement — deferred to a future Portal-Wide Enforcement stage"). This inventory confirms that gap is still open, not newly discovered.

## Live Walkthrough

Not performed as a dev-server click-through — per the approved design's Open Question 4 recommendation, no new user-facing behavior exists in this stage to walk through; every individual feature built across Stages 4–12 already received its own live walkthrough at build time. Verification for this stage is the automated regression run above, run twice (old command vs. corrected command) to make the fix's effect directly visible.

## Risk Notes Carried Forward

- **Eleven modules remain below 90% coverage individually**, even though the aggregate (95.22%) clears the bar: `portal/app.py` (69%), `dispatch/acquisition.py` (71%), `portal/routes/security.py` (76%), `portal/auth_helpers.py` (83%), `dispatch/manager/classify.py` (81%), `portal/helpers.py` (81%), `dispatch/spine/store.py` (86%), `dispatch/manager/priority.py` (86%), `dispatch/scoring.py` (86%), `dispatch/security/store.py` (88%), `dispatch/manager/stage_gate.py` (89%). Three of these gate security-relevant surfaces directly (`portal/auth_helpers.py`, `portal/routes/security.py`, `dispatch/security/store.py`). No new tests were written to close these in this pass — logged here per the approved design, not silently fixed.
- **Neither `stage12-manager-m7-policy-hook` nor this branch has been merged into `main`.** `main` remains 64 files / ~8,941 lines behind. This stage does not resolve that — flagged in the design as Open Question 3, still open.
- **§22 categories #9–#12 (Fact grounding, Publisher no-fabrication, Intelligence verification, Alert governance) have no tests because the underlying cognitive-layer behavior isn't built yet** — not a regression, a reflection of current build scope. #14/#15 (Driver, External Viewer boundaries) are a real, previously-identified gap, not new.

## Effect

The CI coverage gate now measures what it has always claimed to measure. The full aggregate suite (2,489 tests) is certified clean against the corrected gate, on a branch that is the verified full aggregate of Stages 2–12. The §22 inventory gives Stage 14 (Production-Intent Promotion Decision) a concrete, current picture of what testing exists and what doesn't, rather than an assumption.

---

*End of STAGE13_TESTING_HOLD_REVIEW_WALKTHROUGH_REPORT_v1.*
