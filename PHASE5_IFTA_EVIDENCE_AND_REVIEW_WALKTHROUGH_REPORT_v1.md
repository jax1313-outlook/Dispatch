# PHASE5_IFTA_EVIDENCE_AND_REVIEW_WALKTHROUGH_REPORT_v1

## Fuel-Purchase Evidence Linkage + Dispatch-Native IFTA Review Dashboard

**Status:** Implemented and verified. Branch: `phase5-evidence-linkage-review-dashboard`.

**Responds to:** Mike's approval of `DISPATCH_IFTA_PHASE5_LAUNCH_PACKAGE_v2` ("Yes, write it for both" + "Prepare the deployment guide, continue to build using your best judgement"), a direct port of Hold's proven `_resolve_line_evidence()` / worksheet provenance-tracking (`record_ids_by_jurisdiction`) / `build_dashboard()` shapes, adapted to Dispatch's own data model.

---

## What Changed

1. **`dispatch/services.py::_ifta_aggregate()`** — additive provenance tracking: each jurisdiction line in a report now carries `leg_ids`/`purchase_ids` listing exactly which trip-leg and fuel-purchase records contributed to it. Direct port of Hold's `record_ids_by_jurisdiction` pattern from `worksheet.py`. Confirmed not to change the existing tax computation (`total_due` for the standard two-jurisdiction fixture is unchanged at $9.95).
2. **New fuel-purchase evidence layer, deliberately not a reuse of `EvidenceItem`/`attach_evidence()`**: the `evidence` table's `load_id` column is a `NOT NULL` foreign key into `loads`, enforced (`PRAGMA foreign_keys=ON`) — an evidence row for a fuel purchase (which has no load) cannot be inserted there. Built a small, separately-scoped mirror instead:
   - `dispatch/models.py` — `IFTAFuelEvidence` dataclass (checksummed, `purchase_id`-scoped) and `evidence_id: str | None = None` added to `IFTAFuelPurchase`.
   - `dispatch/db.py` — new `ifta_fuel_evidence` table, plus an idempotent `ALTER TABLE ifta_fuel_purchases ADD COLUMN evidence_id TEXT` migration (guarded against `sqlite3.OperationalError` so it's a no-op on a database that already has the column) — the first schema change in this codebase's history that adds a column to a pre-existing table rather than only a new one, so a migration step was actually needed, not just `CREATE TABLE IF NOT EXISTS`.
   - `dispatch/store.py` — CRUD for `ifta_fuel_evidence`.
   - `dispatch/services.py` — `attach_ifta_fuel_evidence()` (mirrors `attach_evidence()`'s checksum/mime-type/`_save_upload()` handling, reusing `_save_upload()` directly), `get_ifta_fuel_evidence_file()`, `list_ifta_fuel_evidence()`, and `resolve_ifta_evidence_for_snapshot()` (direct port of `_resolve_line_evidence()`'s "skip, don't raise" spirit for unresolvable links).
3. **`approve_ifta_quarter()` (Phase 4, extended)** — the sealed compliance record now includes a `resolved_evidence` field from step 2's resolver, called at seal time. No change to the approval/sealing logic itself.
4. **`portal/routes/dispatch_api.py`** — three new routes: `GET/POST /ifta/fuel-purchases/<id>/evidence` (list / attach, mirroring `/loads/<load_id>/evidence`'s two-step pattern), `GET /ifta/fuel-evidence/<id>/download`.
5. **`portal/routes/pages.py` + `portal/templates/ifta_review.html`** — new `/ifta/review` page: read-only, Dispatch-native panel set (tax position, jurisdiction breakdown, plausibility warnings, evidence links, readiness rollup). Deliberately excludes Hold's confirmed-exceptions and suspect-entries panels — Dispatch has no exception-detector framework and no OCR-confidence pipeline to honestly populate them from.
6. **`portal/templates/ifta.html`** — the fuel-purchase list now shows a receipt indicator and an "Attach Receipt" control per purchase (two-step: create the purchase, then attach its receipt — matching the existing load-evidence UI's own create-then-attach pattern rather than a combined form), plus a "Review Dashboard" link.

## Decisions Made Under "Best Judgement" (the package's two open questions)

- **Upload UX:** two-step, mirroring `/loads/<load_id>/evidence` exactly — a fuel purchase is created first, then a receipt is attached to it separately. This was chosen over a combined create+upload form because it's the real, already-proven pattern in this codebase, not a new one.
- **Route name/placement:** `/ifta/review`, as proposed in the package, kept as a separate page rather than a tab on `/ifta` — the two pages have different purposes (data entry vs. read-only readiness check) and Dispatch's other pages don't use an in-page-tab convention.

## What Did Not Change

No exception-detector framework, no OCR/extraction-confidence system. No change to `_ifta_aggregate()`'s tax formula, `IFTA_TAX_RATES`, or Phases 2/3/4's existing behavior — only additive provenance tracking. No change to `EvidenceItem`'s load-scoped semantics. The existing `/ifta` report page is unchanged except for the new receipt-upload control.

## Automated Test Results

Full suite: `python -m pytest -q` — **all tests pass** (run twice; both green), including 30 new tests in `tests/test_ifta_evidence_and_review.py`: provenance-tracking correctness and non-interference with tax totals, evidence attach/refuse-on-unknown-purchase/checksum/file-roundtrip, resolve-skips-not-raises on a deleted purchase and on a legacy pre-Phase-5 snapshot missing the new keys, the sealed record carrying `resolved_evidence`, all new routes (multipart upload, download roundtrip, 400/404 cases), and the review dashboard (zero-data, unlinked-purchase readiness, all-linked "ready to submit", implausible-MPG warning, sealed/frozen state, missing-rate "blocked" without raising through the route, and a structural read-only guard scanning `build_ifta_review_dashboard()`'s source for any `store.create_/update_/delete_` call).

## Live Walkthrough

Run against a live Flask dev server (`portal/app.py`, throwaway `PORTAL_DATA_DIR`/`DISPATCH_ARCHIVE_ROOT`/`DISPATCH_MEMORY_ROOT`/`PORTAL_UPLOAD_DIR`, never real production data) on `127.0.0.1:8105`.

```
POST /api/dispatch/ifta/trip-legs (CA, 1000mi)
POST /api/dispatch/ifta/fuel-purchases (OK, 50gal) -> evidence_id: null
POST /api/dispatch/ifta/fuel-purchases (CA, 20gal) -> evidence_id: null

GET /ifta/review?year=2025&quarter=1
  -> "2 of 2 fuel purchase(s) have no receipt attached"

POST /api/dispatch/ifta/fuel-purchases/<OK purchase>/evidence (multipart, receipt.pdf)
  -> 201, checksum computed, file written to PORTAL_UPLOAD_DIR
GET  /api/dispatch/ifta/fuel-purchases -> OK purchase now shows evidence_id
GET  /api/dispatch/ifta/fuel-evidence/<id>/download -> bytes match the uploaded file exactly

GET /ifta/review?year=2025&quarter=1
  -> "1 of 2 fuel purchase(s) have no receipt attached", receipt.pdf shown against the OK line

POST /api/dispatch/ifta/report-approvals {year:2025, quarter:1} -> 201, draft
Real .eml written to archive/CIN/Outbox/ifta-approval-<id>.eml (no SMTP configured);
decoded (quoted-printable) to recover the actual HMAC approval token.

GET .../approve?token=wrong -> 403
GET .../approve?token=<real> -> 200, "Quarter Sealed"

Compliance/ifta_sealed_report/<id>.json -- resolved_evidence present:
  CA: [(purchase_id, evidence=None)]
  OK: [(purchase_id, evidence.original_filename="receipt.pdf")]
archive/CIN/Compliance/ -- confirmed does NOT exist (no accidental nesting, same guarantee Phase 4 proved)

GET /ifta/review?year=2025&quarter=1
  -> readiness "sealed", "showing the frozen, approved snapshot", receipt.pdf still shown

GET /ifta?year=2025&quarter=1
  -> "Review Dashboard" link present, "Attach Receipt" control present on fuel-purchase rows
```

All scenarios behaved exactly as designed, including the two hazards this design specifically checked for: fuel-purchase evidence never collided with the load-scoped `evidence` table's foreign-key constraint, and compliance records stayed a sibling of `CIN`, never nested under it. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.
