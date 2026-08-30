# PHASE7_SUSPECT_ENTRIES_WALKTHROUGH_REPORT_v1

## Suspect Entries — Surfacing Low-Confidence Scanned Fuel Purchases

**Status:** Implemented and verified. Branch: `phase7-suspect-entries`.

**Responds to:** Mike's request to resolve `DISPATCH_IFTA_PHASE7_SUSPECT_ENTRIES_LAUNCH_PACKAGE_v1`'s one open question myself ("please answer question") and proceed — a small, direct port of Hold's `_suspect_entries()` contract, closing the gap Phase 6b left open (`extraction_confidence` computed on every scan, discarded on save).

---

## What Changed

1. **`dispatch/models.py` / `dispatch/db.py`** — `IFTAFuelPurchase` gains `extraction_confidence: float | None = None`, plus another idempotent `ALTER TABLE` migration (the same mechanism Phase 5 introduced for exactly this situation).
2. **`dispatch/services.py`**:
   - `add_ifta_fuel_purchase()` gains an optional `extraction_confidence` parameter, passed straight through — `None` for every manually-entered purchase.
   - `DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD = 0.75` — Hold's own placeholder value, carried over with the same "not yet calibrated" framing.
   - `list_suspect_ifta_fuel_purchases(year, quarter, vehicle_id="", threshold=...)` — read-only, reuses the existing `list_ifta_fuel_purchases()` call and filters in Python; no new SQL query path.
   - `build_ifta_review_dashboard()` gains a `suspect_entries` list, always computed live (present identically whether the quarter is draft or sealed — unlike the Exceptions panel, which reads a frozen snapshot once sealed) and **never factored into `readiness_status`**.
3. **`portal/routes/dispatch_api.py`** — `POST /ifta/fuel-purchases` accepts an optional `extraction_confidence` body field.
4. **`portal/templates/ifta.html`** — the scan flow already received `extraction_confidence` (Phase 6b); this only stops discarding it, carrying `scannedConfidence` into the create-purchase payload.
5. **`portal/templates/ifta_review.html`** — new "Suspect Entries" panel: date, vendor, jurisdiction, confidence, and whether a receipt is attached, for every purchase below threshold in the period.

## The Resolved Open Question

**Should suspect-entry count factor into the readiness rollup, the way unlinked-evidence and exception counts already do?** Resolved **no**. Matches Hold's own precedent (suspect entries are explicitly informational, never governed the way confirmed exceptions are), and two things support it holding here: the dispatcher already reviewed and could correct the extracted values before clicking Save, so a low score afterward is a weaker signal than a hard exception like `fuel_no_miles`; and the 0.75 threshold is an uncalibrated placeholder — folding an unproven number into the top-line "ready to submit" status would let it downgrade an otherwise-fine quarter.

## Automated Test Results

Full suite: `python -m pytest -q` — **all tests pass**, including 21 new tests in `tests/test_ifta_suspect_entries.py` (confidence persistence for manual vs. scanned entries, threshold boundary — exactly-at-threshold excluded, matching Hold's strict `<` — quarter scoping, custom thresholds, the route's optional/null/present cases, suspect entries present on both draft and sealed dashboards, suspect entries **not** affecting `readiness_status`, the blocked-dashboard edge case, template rendering, and a structural read-only guard).

## Live Walkthrough

Run against a live Flask dev server (`portal/app.py`, throwaway data dirs, never real production data) on `127.0.0.1:8108`.

```
POST /api/dispatch/ifta/fuel-purchases (OK, confidence 0.41 -- a real low-confidence scan)
POST /api/dispatch/ifta/fuel-purchases (CA, confidence 0.93 -- a real high-confidence scan)
POST /api/dispatch/ifta/fuel-purchases (TX, no confidence field -- a real manual entry)
  -> all three persisted with the exact confidence value sent, or null for the manual one

GET /ifta/review?year=2025&quarter=1
  -> "Suspect Entries (1)": only the 0.41 OK purchase, vendor and confidence shown correctly
  -> readiness_status: "3 of 3 fuel purchase(s) have no receipt attached" (unaffected by the suspect entry)

Attached receipts to all three purchases
GET /ifta/review?year=2025&quarter=1
  -> readiness_status: "2 exception(s) noted" (Phase 6a's fuel_no_miles firing for CA and TX,
     which have fuel purchases but no trip legs in their jurisdiction -- real, correct behavior)
  -> Suspect Entries (1) still shown, now with "receipt attached" noted, entirely independent
     of the exceptions panel and the readiness status it drives
```

This last step was the clearest possible proof the two panels are genuinely decoupled: a quarter with real governed exceptions *and* an informational suspect entry, shown simultaneously, with only the exceptions affecting the readiness rollup — exactly as designed. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.
