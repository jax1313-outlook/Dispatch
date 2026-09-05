# PHASE4_IFTA_FINALIZATION_GATE_WALKTHROUGH_REPORT_v1

## IFTA Quarter Approval / Finalization Gate

**Status:** Implemented and verified. Branch: `phase4-ifta-finalization-gate`.

**Responds to:** Mike's approval of `DISPATCH_IFTA_PHASE4_FINALIZATION_GATE_LAUNCH_PACKAGE_v3` ("Quarterly only for now, single reviewer is fine"), itself a direct port of Hold's proven `src/dispatch/ifta_clerk/prepare.py` / `src/dispatch/ifta/package.py` / `src/dispatch/ifta_clerk/recommend.py` pipeline, adapted to Dispatch's architecture (no Queue, no persisted worksheet table — both added here as their Dispatch-native equivalents).

---

## What Changed

1. **`dispatch/db.py` / `dispatch/models.py` / `dispatch/store.py`** — new `ifta_report_approvals` table + `IFTAReportApproval` dataclass + CRUD, holding a frozen `_ifta_aggregate()` snapshot per (year, quarter, vehicle_id), with a `draft`→`sealed` status lifecycle. This is the one genuinely new piece of infrastructure Dispatch needed that Hold already had (a persisted worksheet-equivalent).
2. **`dispatch/services.py`**:
   - `submit_ifta_quarter_for_approval()` — freezes the current computed report into a new `draft` approval row, emails the reviewer an HMAC-signed approval link (reusing `cin_lite.email_delivery`'s existing generic `make_token`/`verify_token`/`send`, not a new token implementation). Refuses a second submission of the same period, ever — direct port of Hold's `AlreadySubmittedError` semantics.
   - `approve_ifta_quarter()` — verifies the token, then seals: archives the frozen snapshot and a computed payment recommendation, flips status to `sealed`. Idempotent on an already-sealed approval (a repeat click is a no-op success, matching Hold's `attempt_seal()`), only re-checking the token when there's something left to do.
   - `compute_ifta_payment_recommendation()` — pure function, direct port of Hold's `compute_payment_recommendation()`: labels the sealed `total_due` as `remit`/`credit`/`no_payment_due`. No network import anywhere in it (guarded by a structural test, mirroring Hold's own technique).
   - `_write_compliance_record()` / `_resolve_compliance_root()` — the same SHA-256-sidecar write-and-hash technique Phase 3 proved in `cin_lite/archive.py`, reimplemented locally (not cross-imported) so IFTA compliance records land in their own `<DISPATCH_ARCHIVE_ROOT>/Compliance/` folder — a sibling of `cin_lite/archive.py`'s `CIN` subtree, not nested under it, per Phase 3's own "two unrelated archives" finding.
3. **`portal/routes/dispatch_api.py`** — four new routes: `POST/GET /ifta/report-approvals` (submit / list), `GET /ifta/report-approvals/<id>` (detail), `GET /ifta/report-approvals/<id>/approve` (the emailed link's target).
4. **`portal/routes/pages.py` + `portal/templates/ifta.html`** — the `/ifta` page (quarterly view only, per Mike's answer) now shows a DRAFT / SUBMITTED / SEALED status badge and a "Submit for Approval" button, with the payment recommendation displayed once sealed.
5. **`portal/templates/ifta_approval_decision.html`** — new template for the emailed approval link's landing page, mirroring the existing `dispatch_decision.html`/`decision.html` pattern already used for load and contract decisions.

## What Did Not Change

No real QuickBooks/accounting/payment API integration — confirmed via Mike's direction and Hold's own precedent (`recommend.py`'s docstring: *"no payment API, no bank integration, no accounting write exists anywhere in this codebase, and this module doesn't add one"*). No change to `_ifta_aggregate()`'s formula, `IFTA_TAX_RATES`, or Phases 2/3's existing hardening. No change to `portal/models/publisher.py` or `Settlement`/driver-pay/customer-invoicing — neither was needed once Hold's actual proven design was found to use neither. Monthly IFTA view is unaffected — no approval workflow attached to it, per Mike's "quarterly only for now."

## Automated Test Results

Full suite: `python -m pytest -q` — **all tests pass**, including 28 new tests in `tests/test_ifta_report_approvals.py` (submission, double-submission refusal even after underlying data changes, missing-rate refusal still propagating through the new path, token verification, idempotent re-seal, compliance-archive writes landing outside the CIN subtree, the payment-recommendation pure-function cases, the structural no-network-import guard, and route/template coverage for every new endpoint and status badge).

## Live Walkthrough

Run against a live Flask dev server (`python portal/app.py`, throwaway `PORTAL_DATA_DIR`/`DISPATCH_ARCHIVE_ROOT`, never real production data) on `127.0.0.1:8101`.

**Full pipeline, real data, real email:**
```
POST /api/dispatch/ifta/trip-legs (CA, 1000mi) + fuel-purchases (OK, 50gal) -> 201s
GET  /ifta?year=2025&quarter=1 -> DRAFT badge + "Submit for Approval" button present

POST /api/dispatch/ifta/report-approvals {year:2025, quarter:1}
  -> 201, snapshot frozen: total_due = $9.95 (CA taxable 50gal @ 0.389, OK credit -50gal @ 0.19)
POST (same period again) -> 409 {"error": "2025 Q1 was already submitted for approval..."}
GET  /ifta?year=2025&quarter=1 -> "SUBMITTED — AWAITING APPROVAL" badge

Real .eml written to Archive/Outbox/ifta-approval-<id>.eml (no SMTP configured);
decoded (quoted-printable) to recover the actual approval link + HMAC token.

GET .../approve?token=wrong    -> 403, "Approval Failed" rendered cleanly
GET .../approve?token=<real>   -> 200, "Quarter Sealed", approved_by reviewer@dispatch.local,
                                   recommendation: remit — $9.95
GET .../approve?token=garbage  -> 200 anyway (idempotent: already sealed, nothing to verify)

Compliance/ifta_sealed_report/<id>.json(.sha256)          -- present
Compliance/ifta_payment_recommendation/<id>.json(.sha256) -- present
CIN/Compliance/ -- confirmed does NOT exist (no accidental nesting under the CIN subtree)

GET /ifta?year=2025&quarter=1 -> "SEALED" badge + "remit" recommendation shown
```

All scenarios behaved exactly as designed, including the one architectural hazard this design deliberately avoided (nesting compliance records under `cin_lite/archive.py`'s CIN-specific root) and the one behavioral choice ported faithfully from Hold (idempotent re-approval rather than raising on a repeat click). The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.

## Risk Notes Carried Forward

- QuickBooks remains a deliberate non-integration, per Mike's explicit direction — the payment recommendation is the entire action, same as Hold's proven design.
- Approval authentication is the single `DISPATCH_EMAIL_REVIEWER` address, per Mike's "single reviewer is fine" — reusing the same authentication model already in production use for contract and load decisions.
- Monthly IFTA filing has no approval workflow attached — quarterly only, per Mike's direction; revisit if monthly filing becomes a real requirement.

---

*End of PHASE4_IFTA_FINALIZATION_GATE_WALKTHROUGH_REPORT_v1.*
