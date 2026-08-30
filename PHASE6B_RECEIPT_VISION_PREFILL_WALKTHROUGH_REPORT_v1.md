# PHASE6B_RECEIPT_VISION_PREFILL_WALKTHROUGH_REPORT_v1

## Vision-Assisted Fuel-Receipt Pre-Fill — A Deliberately Narrow Slice, Not Hold's Lane C

**Status:** Implemented and verified. Branch: `phase6b-receipt-vision-prefill`.

**Responds to:** Mike's approval of both Phase 6 launch packages together ("Approved both, use your best judgement"), following `DISPATCH_IFTA_PHASE6B_RECEIPT_VISION_PREFILL_LAUNCH_PACKAGE_v1` — a narrow, honestly-scoped slice of Hold's Lane C receipt-intake pipeline, built to match Dispatch's own established Claude-agent pattern rather than Hold's separate `ClaudeVisionExtractor` class.

---

## What Changed

1. **`cin_lite/agents/receipt_vision.py`** (new) — `extract_fuel_receipt(image_bytes, filename)`: sends one receipt image to Claude via `anthropic.Anthropic()` with a JSON-schema-constrained response (vendor name/address, purchase date, gallons, amount, `extraction_confidence`), mirroring `cin_lite/agents/extractor.py`'s exact real pattern (`ANTHROPIC_API_KEY`/`DISPATCH_MODEL` env vars, broad-except fallback) rather than importing Hold's `ClaudeVisionExtractor`. No API key, package not installed, unsupported file extension, and any call/parse failure all degrade identically to `{"available": False, "reason": ...}` — never a raised exception, never a fabricated result.
   - `derive_jurisdiction(vendor_address)` — small, direct port of Hold's `src/dispatch/receipt/address.py` deterministic state-code pattern match, sourced from Dispatch's own `IFTA_JURISDICTIONS` list (not a hand-duplicated copy) so it can never drift out of sync with what Dispatch actually accepts. Returns `None` rather than raising when no code is found — a pre-fill convenience, not a gate with anywhere to quarantine to.
2. **`portal/routes/dispatch_api.py`** — new `POST /ifta/fuel-purchases/extract-receipt`: a pre-fill lookup only, creates no fuel purchase and no evidence row. Always returns 200 with either extracted fields or `available: false`; the one genuine client error is no file at all (400).
3. **`portal/templates/ifta.html`** — the Add Fuel Purchase form gains a "Scan Receipt" file input above the manual fields. On selection, it POSTs to the extract endpoint and pre-fills the (still fully editable) jurisdiction/gallons/amount/date/vendor fields, with a confidence-colored status line. On the dispatcher's explicit "Save Fuel Purchase" click (unchanged trigger), the purchase is created first, then — only if a receipt was scanned — the same image is immediately attached as its evidence via Phase 5's existing `attach_ifta_fuel_evidence()` endpoint. Nothing auto-submits.

## What This Deliberately Does Not Port

No drop folder, no queue/task system, no vendor-profile CSV matching, no fuel-card statement parser, no multi-transaction-per-document routing. This covers only the single-receipt, scan-to-pre-fill path — Hold's Lane C is a much larger system, and building the rest of it wasn't implied by "OCR," as the launch package stated plainly up front.

## Decisions Made Under "Best Judgement"

- **`extraction_confidence` is discarded, not persisted** on the saved `IFTAFuelPurchase` — the dispatcher's explicit Save is the human-confirmation step this whole codebase already leans on. A future "suspect entries" dashboard panel would need this persisted; that's a separate decision, not bundled in here.
- **Shipped with the graceful-fallback path as what actually gets exercised live** — no real `ANTHROPIC_API_KEY` exists in this build/deploy environment, confirmed again this pass. The live-extraction code path is real code, but — same honesty Hold's own README states for `ClaudeVisionExtractor` — untested against a live call in this environment.

## Automated Test Results

Full suite: `python -m pytest -q` — **all tests pass**, including 18 new tests in `tests/test_ifta_receipt_vision.py` (no-key fallback, unsupported extension, successful extraction via the fake-`anthropic` fixture `tests/conftest.py` already provides for `cin_lite`'s other agents, API failure/malformed-JSON/invalid-shape all degrading to `available: false`, never raising, `derive_jurisdiction()`'s token-boundary correctness including a substring-false-positive guard ("CAMP" must not match "CA") and a Canadian province code, the route's 400/200 cases, confirmation the extract call creates nothing, and a full scan-then-create-then-attach composition test proving the new endpoint and Phase 5's existing evidence-attach endpoint compose correctly).

## Live Walkthrough

Run against a live Flask dev server (`portal/app.py`, throwaway data dirs, `ANTHROPIC_API_KEY` explicitly unset, never real production data) on `127.0.0.1:8107`.

```
POST /api/dispatch/ifta/fuel-purchases/extract-receipt (real image bytes, no API key configured)
  -> 200 {"available": false, "reason": "no API key configured"}
POST (no file) -> 400
GET  /api/dispatch/ifta/fuel-purchases -> [] (confirmed the extract call created nothing)

GET /ifta -> "Scan Receipt (optional -- pre-fills the fields below)" control present,
             fuel-scan-input / scanReceipt() wired into the page
```

Since this environment has no real Anthropic API key, the `available: true` path was demonstrated the same way `tests/test_ifta_receipt_vision.py` proves it — a fake `anthropic` module injected via the identical technique `tests/conftest.py`'s own `install_anthropic` fixture uses — but run as a standalone script against the same live SQLite database the walkthrough server was using, exercising the real `receipt_vision.extract_fuel_receipt()` → `derive_jurisdiction()` → `services.add_ifta_fuel_purchase()` → `services.attach_ifta_fuel_evidence()` chain end to end:

```
extraction result: {available: true, vendor_name: "Love's Travel Stop",
  vendor_address: "789 Highway Blvd, Tulsa, OK 74103", purchase_date: "2025-02-01",
  gallons: 61.4, amount: 215.9, extraction_confidence: 0.88}
derived jurisdiction: OK
created purchase: FUEL-...  OK  61.4
attached evidence: FUELEV-...
purchase now has evidence_id: True
```

Both the honest-fallback path (real, live, actually exercised against the running server) and the full pre-fill-to-save composition (real code, mocked model call, actually exercised against the same database) behaved exactly as designed. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.
