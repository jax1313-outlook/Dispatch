# PHASE6A_IFTA_EXCEPTION_DETECTORS_WALKTHROUGH_REPORT_v1

## IFTA Exception Detectors — Six of Hold's Ten, Ported Honestly

**Status:** Implemented and verified. Branch: `phase6a-ifta-exception-detectors`.

**Responds to:** Mike's approval of both Phase 6 launch packages together ("Approved both, use your best judgement"), starting with `DISPATCH_IFTA_PHASE6A_EXCEPTION_DETECTORS_LAUNCH_PACKAGE_v1` — a direct port of six of Hold's ten proven detectors (`src/dispatch/ifta/exceptions.py`) to Dispatch's actual field names, deliberately leaving out the four that need infrastructure Dispatch doesn't have.

---

## What Changed

1. **`dispatch/services.py`** — six detector functions (`_detect_fuel_no_miles`, `_detect_miles_no_fuel_gap`, `_detect_fleet_mpg_out_of_band`, `_detect_broken_evidence_linkage`, `_detect_late_arrival_closed_quarter`, `_detect_corner_clipping`), a private orchestrator (`_run_ifta_exception_detectors_on_snapshot()`) and a public read-only entrypoint (`run_ifta_exception_detectors(year, quarter, vehicle_id="")`) that resolves the live-or-sealed snapshot and runs all six against it.
   - `_detect_broken_evidence_linkage` is a genuinely new capability, not in Hold's original form — it re-hashes each linked fuel-purchase receipt and compares against the checksum recorded at attach time (Phase 5), the same fail-closed technique Phase 3 proved for the archive layer.
   - `_detect_late_arrival_closed_quarter` compares live trip-leg/fuel-purchase IDs for a period against the `leg_ids`/`purchase_ids` frozen into that period's sealed `IFTAReportApproval` snapshot (Phase 5's provenance tracking) — anything present live but absent from the frozen snapshot arrived after sealing.
2. **`submit_ifta_quarter_for_approval()` (Phase 4, extended)** — runs the six detectors against the just-frozen snapshot at submission time and persists every finding to a new `ifta_exceptions` table, tied to the new `approval_id`. Advisory only: findings never block submission, matching Hold's own "never auto-resolves" principle.
3. **`dispatch/models.py` / `dispatch/db.py` / `dispatch/store.py`** — new `IFTA_EXCEPTION_TYPES`, `IFTAException` dataclass, `ifta_exceptions` table, and CRUD (`create_ifta_exception`, `list_ifta_exceptions`).
4. **`portal/routes/dispatch_api.py`** — new `GET /ifta/report-approvals/<id>/exceptions`.
5. **`build_ifta_review_dashboard()` / `portal/templates/ifta_review.html`** — the Exceptions panel replaces Phase 5's ad hoc "Plausibility Warnings" panel (per the launch package's default answer to Open Question 1). For a draft/live quarter, exceptions are computed fresh on every view; for a sealed quarter, the dashboard reads the persisted `ifta_exceptions` rows rather than re-running the detectors — confirmed by the walkthrough (see below) that a post-seal file tamper does *not* retroactively change what a sealed quarter's dashboard shows.

## What Did Not Port (Named, Not Silently Dropped)

`odometer_discontinuity`, `active_truck_days_no_mileage`, `rate_version_mismatch`, `reefer_in_propulsion` — each needs infrastructure Dispatch genuinely doesn't have (an odometer field, a period-based mileage-record concept, rate-table versioning, tractor/reefer tagging), not just more code. No Lane-B-equivalent queue/task system — exceptions surface only on the review dashboard, never as a separate actionable inbox item.

## Automated Test Results

Full suite: `python -m pytest -q` — **all tests pass**, including 22 new tests in `tests/test_ifta_exception_detectors.py` (each detector's fire/silent boundary, broken-evidence-linkage for both a deleted file and a tampered one, late-arrival firing only after sealing and only for genuinely new records, submission-time persistence tied to the right approval, the sealed dashboard reading persisted findings rather than re-detecting live, the route, and a structural read-only guard on both the public and private detector-running functions). Two existing Phase 5 tests updated (`warnings` → `exceptions`) to match the panel replacement; both still assert the same underlying `fleet_mpg_out_of_band` behavior.

## Live Walkthrough

Run against a live Flask dev server (`portal/app.py`, throwaway data dirs, never real production data) on `127.0.0.1:8106`.

```
Seeded: CA (250mi + 50gal, clean), OK (20gal, 0 miles), TX (1000mi, 0 fuel), NV (2mi)

GET /ifta/review?year=2025&quarter=1
  -> "Exceptions (4)": fuel_no_miles (OK), miles_no_fuel_gap (TX),
     fleet_mpg_out_of_band (17.89 outside [4.0, 9.5]), corner_clipping (NV)

POST .../fuel-purchases/<CA purchase>/evidence (receipt.pdf) -> attached
GET /ifta/review -> no broken_evidence_linkage (file intact)

Tampered the stored receipt file's bytes directly on disk
GET /ifta/review -> broken_evidence_linkage: "receipt file content no longer
                     matches its recorded checksum" -- fired correctly
Restored the file -> exception cleared on the next view

POST /api/dispatch/ifta/report-approvals {year:2025, quarter:1} -> 201, draft
GET  .../report-approvals/<id>/exceptions -> all 4 findings persisted,
     each with correct related_record_ids (e.g. fuel_no_miles ->
     [FUEL-...-BDB286F2])

Decoded the real .eml, sealed via the real HMAC token -> 200 "Quarter Sealed"

Added a late trip leg (AZ, 300mi, dated inside the now-sealed quarter)
GET /ifta/review (sealed) -> still shows the original 4 persisted exceptions,
     NOT the new late arrival -- confirms sealed dashboards read frozen data
run_ifta_exception_detectors(2025, 1) called directly against the same live
     data -> correctly reports late_arrival_closed_quarter for the AZ leg
```

Every scenario behaved exactly as designed, including the one behavior this design specifically checked for: a sealed quarter's Exceptions panel reflects what was true *at seal time*, not what's true *right now* — the same "frozen means frozen" guarantee Phase 4's tax position and Phase 5's evidence bundle already rely on. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.
