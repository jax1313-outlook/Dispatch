# PHASE2_IFTA_WALKTHROUGH_REPORT_v1

## Refuse-on-Missing-Rate + Mileage Plausibility Warning

**Status:** Implemented and verified. Branch: `phase2-ifta-missing-rate-hardening`.

**Responds to:** Mike's approval of `DISPATCH_IFTA_PHASE2_LAUNCH_PACKAGE_v1` ("approved perform"), which itself followed his "OWNER RESPONSE" approving Phase 1 (process discipline) and Phase 2 (IFTA missing-data hardening) for planning, with the explicit instructions: use Dispatch as the target; use Hold only as reference/proven pattern; do not import Hold wholesale; do not replace the Dispatch IFTA engine; do not alter unrelated Dispatch capabilities.

This report is the first artifact in Dispatch produced under Phase 1's process discipline (a walkthrough report + decision record before anything merges), applied here to Phase 2's own work, per the launch package's own Section 8 proposal.

---

## What Changed

1. **`dispatch/services.py`** — `_ifta_aggregate()` now refuses (raises `ValueError` naming every missing jurisdiction) instead of silently substituting a `{"rate": 0.0, "surcharge": 0.0}` fallback for any jurisdiction with no entry in `IFTA_TAX_RATES`. A jurisdiction with a genuine, stored `0.0` rate is unaffected — the check is a membership test (`not in`), never a truthiness test.
2. **`dispatch/services.py`** — `add_ifta_trip_leg()` now computes a fleet-MPG estimate for the trip leg's quarter (built independently of `IFTA_TAX_RATES` and of `_ifta_aggregate()`, from the same `list_ifta_trip_legs()`/`list_ifta_fuel_purchases()` primitives) and attaches a non-blocking `plausibility_warning` field to the returned dict when that estimate falls outside `DEFAULT_MPG_BAND = (4.0, 9.5)`. The entry is never refused or rolled back.
3. **`portal/routes/pages.py`** — the `/ifta` page route now wraps its report calls in `try/except ValueError`, passing `error=str(exc)` to the template instead of letting the exception reach the user as an unhandled 500. (Finding 2 from the launch package — the sibling API routes already had this handling; the page route did not.)
4. **`portal/templates/ifta.html`** — renders a clean error banner when `error` is set, and gracefully omits the report-dependent sections (summary cards, report table, trip/fuel lists) rather than crashing on a `None` report. The add-trip/add-fuel forms remain available regardless.
5. **Tests** — replaced the one existing test that touched this path (which only re-executed `dict.get()` standalone, never calling `_ifta_aggregate()`) with a real refusal test; added a genuine-zero-rate protection test, a page-route clean-error test, and plausibility-warning fire/silent/insufficient-data tests confirming the trip leg is persisted in all cases.

## What Did Not Change

Exactly as scoped: no change to `IFTA_TAX_RATES`'s or `IFTA_JURISDICTIONS`'s contents, no rate-table versioning or editing UI, no changes to the load board, brokers, fleet, billing, driver pay, compliance, or calendar pages, no changes to `cin_lite`, `sync`, or CI configuration. No Hold code, schema, or class was imported — Hold's `MissingRateError` and `live_fleet_mpg_estimate()` were used only as proven reference patterns, restated in Dispatch's own words and against Dispatch's own data model.

## Automated Test Results

Full suite: `python -m pytest -q` from the repo root — **all tests pass** (no failures, no errors), including the 5 new/replaced tests and every pre-existing test in `tests/test_ifta_monthly.py` and `tests/test_ifta_mileage.py`, plus the full remaining suite (`cin_lite`, `sync`, other `portal` routes) untouched and green.

## Live Walkthrough (per Section 8 of the launch package)

Run against a live Flask dev server (`python portal/app.py`, `PORTAL_DATA_DIR` pointed at a throwaway temp directory — never against real `D:\Dispatch Operations` data) on `127.0.0.1:8099`, plus one scenario run through the app's real WSGI test client (identical routing/view/template code path; used only because it requires an in-process rate removal that only makes sense for a single ephemeral run).

**1. Happy path (unaffected behavior):**
```
POST /api/dispatch/ifta/trip-legs   {"jurisdiction":"TX","miles":500,...}      -> 201
POST /api/dispatch/ifta/fuel-purchases {"jurisdiction":"TX","gallons":80,...}  -> 201
GET  /api/dispatch/ifta/report?year=2025&quarter=1                            -> 200, tax_rate 0.2, total_due computed normally
GET  /ifta?year=2025&quarter=1                                                -> 200
```

**2. Mileage plausibility warning (non-blocking):**
```
POST fuel-purchases (CA, 10 gal)         -> 201
POST trip-legs (CA, 600 mi, same quarter) -> 201, body includes:
  "plausibility_warning": "fleet_mpg 60.00 outside plausible range [4.0, 9.5] for this period — mileage or fuel entry may be off"
GET  trip-legs?jurisdiction=CA            -> confirms the leg is persisted (not refused)
```

**3. Refuse-on-missing-rate + clean page error (Findings 1 & 2):**
```
Trip leg recorded for TX, then TX's entry removed from IFTA_TAX_RATES in-memory
(simulating the future list-drift Finding 1 warns is currently unguarded against)

GET /api/dispatch/ifta/report?year=2025&quarter=1
  -> 400 {"error": "No IFTA tax rate on file for jurisdiction(s) ['TX'] — refusing
          to report a fabricated $0.00 rate. Add the missing rate(s) to
          IFTA_TAX_RATES before generating this report."}

GET /ifta?year=2025&quarter=1
  -> 200 (not 500), page body contains "Unable to generate this report" and
     names the missing jurisdiction ("TX")
```

All three scenarios behaved exactly as designed. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.

## Risk Notes Carried Forward From the Launch Package

- `DEFAULT_MPG_BAND = (4.0, 9.5)` is copied from Hold's own proven value, tuned against Hold's synthetic data — not yet reviewed against Dispatch's real equipment profile. Flagged in code as a starting point, not a final calibration.
- The portal frontend's handling of the new `plausibility_warning` field (beyond simply being present in the JSON response) was explicitly out of scope for this pass, per the launch package.

---

*End of PHASE2_IFTA_WALKTHROUGH_REPORT_v1.*
