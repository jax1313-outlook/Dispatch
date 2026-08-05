# PHASE3_ARCHIVE_WALKTHROUGH_REPORT_v1

## Content-Hash Verification for `cin_lite/archive.py`

**Status:** Implemented and verified. Branch: `phase3-archive-integrity-hashing`.

**Responds to:** Mike's approval of `DISPATCH_ARCHIVE_PHASE3_LAUNCH_PACKAGE_v1` ("fail closed, approved perform"), answering the package's one open design question (fail-closed vs. non-blocking warning) in favor of fail-closed, matching Hold's proven `EvidenceSpine` pattern and this series' "refuse rather than fabricate/serve-corrupted-data" principle.

---

## What Changed

1. **`cin_lite/archive.py`** — every artifact write (`_write_json()`'s JSON writes across `Raw`/`Processed`/`Intelligence`/`Routing`/`Proposals`, plus `store()`'s Summaries `.txt` and `store_proposal()`'s `.md` outline) now goes through a shared `_write_and_hash()` helper that persists a `.sha256` sidecar alongside the artifact. `load_artifact()` and `list_contracts()` now both route reads through a shared `_read_verified()` helper: no sidecar → read through unchanged (pre-Phase-3 artifacts), sidecar matches → unchanged (the normal case), sidecar mismatches → raise the new `ArchiveIntegrityError` and escalate via a new `record_integrity_exception()`.
2. **`record_integrity_exception()`** writes a distinctly-named file (`Routing/{contract_id}.integrity-exception-{id}.json`, `route: "HUMAN_REVIEW"`) rather than calling `record_routing()` — the launch package's Finding (Section 3) identified that `record_routing()` always overwrites the single `Routing/{contract_id}.json` file, which would destroy the very evidence a mismatch in that file is meant to preserve. Verified live (Section "Live Walkthrough" below) that this still surfaces correctly in the existing `routing_history(route_filter="HUMAN_REVIEW")` queue without touching the contract's real routing decision.
3. **`portal/routes/pipeline.py`** — `archive_list()` and `archive_detail()` (both JSON API routes) now catch `ArchiveIntegrityError` and return a clean `{"error": ...}, 500` instead of an unhandled crash.
4. **`portal/routes/pages.py` + `portal/templates/archive.html`** — the `/archive` page route catches the same exception and renders a clean error banner in the "DISPATCH Pipeline Archive" section instead of crashing the whole page; the rest of the page (sandbox/decision/publisher archive sections) is unaffected since they don't depend on `cin_lite.archive`.
5. **Scope discovered and extended during implementation, beyond the launch package's literal text:** the package's Section 5 named `load_artifact()` as "the single function every caller uses to read archive artifacts back," but `list_contracts()` independently reads `Processed/*.json` via its own `glob()`, bypassing `load_artifact()` entirely. Left unverified, a corrupted `Processed` record would be silently listed by `list_contracts()` (`/api/pipeline/archive`, the `/archive` page) while `load_artifact()` correctly refused it on the detail view — an inconsistent, confusing half-fix. `list_contracts()` was brought under the same `_read_verified()` path, and its two callers (`archive_list()`, `archive_view()`) got the same exception handling as `archive_detail()`. Flagging this explicitly since it's real scope beyond what was approved in writing, even though it's the same pattern applied to a sibling reader of the identical file type, not a new capability.

## What Did Not Change

`cin_lite/archive.py`'s folder layout, JSON record shapes, `make_id()`'s ID scheme, and `record_routing()`'s behavior for real human/API-driven decisions — all unchanged. `portal/models/archive.py` (the unrelated operational archive, per the launch package's Section 2 finding) — not touched. `control.py`'s `ACTIONS` dict, email rendering, and token verification — not touched. No retroactive hashing of pre-existing artifacts.

## Automated Test Results

Full suite: `python -m pytest -q` from the repo root — **all tests pass**. One pre-existing test (`tests/test_storage_routing.py::TestCINArchiveRouting::test_cin_archive_write`) asserted "exactly one file in the Raw directory" as an implementation detail; updated its assertion to count `.json` files specifically (its actual intent — verifying the write landed under the correct root), since a `.sha256` sidecar now legitimately exists alongside it. Nine new tests added across `tests/test_archive.py` (write-side sidecar coverage, backward-compat with no sidecar, matching-hash pass-through, corrupted-artifact raise + single escalation file, `HUMAN_REVIEW` queue pickup, Routing-subdir-mismatch-does-not-overwrite, `list_contracts()` verification), plus two in `tests/test_pipeline_api.py` (clean 500 on both API routes) and one in `tests/test_portal.py` (clean error banner on the `/archive` page).

## Live Walkthrough

Run against a live Flask dev server (`python portal/app.py`, `PORTAL_DATA_DIR`/`DISPATCH_ARCHIVE_PATH` pointed at throwaway temp directories — never real production data) on `127.0.0.1:8100`.

**1. Real pipeline run, approval, and sidecar creation (happy path):**
```
POST /api/pipeline/run          -> 2 real sample contracts processed
POST /api/pipeline/decide {"contract_id": "CIN-...-D0ED1187", "action": "approve_archive"}
  -> route: ARCHIVE

Sidecar files confirmed on disk, one per artifact:
  Raw/CIN-...json.sha256, Processed/...json.sha256, Intelligence/...json.sha256,
  Summaries/...txt.sha256, Routing/...json.sha256

GET /api/pipeline/archive/CIN-...-D0ED1187  -> 200, full detail returned correctly
```

**2. Tampering + fail-closed behavior (the core of this phase):**
```
Directly overwrote Processed/CIN-...-D0ED1187.json on disk with unrelated content
(simulating corruption or tampering, bypassing the application entirely)

GET /api/pipeline/archive/CIN-...-D0ED1187
  -> 500 {"error": "content hash mismatch reading Processed/CIN-...json:
          expected 07c9606b..., got 7943c520..."}

GET /api/pipeline/archive (list route)
  -> 500 {"error": "content hash mismatch reading Processed/CIN-...json: ..."}

GET /archive (HTML page)
  -> 200 (not 500), page body contains:
     "Unable to load this section: content hash mismatch reading Processed/..."
```

**3. Escalation correctness (verifying Finding/Section 3's fix):**
```
GET /api/pipeline/queue/HUMAN_REVIEW
  -> 3 records for CIN-...-D0ED1187 (one per read attempt above), each with
     flags: ["archive_integrity_mismatch"], action_label: "Flag for review
     (auto: archive integrity mismatch)"

Routing/CIN-...-D0ED1187.json (the real approve_archive decision) read
directly from disk afterward:
  action: approve_archive | route: ARCHIVE   <- confirmed UNCHANGED

ls Routing/ showed the real file plus three separate
  CIN-...-D0ED1187.integrity-exception-{id}.json files -- no collision,
  no overwrite, exactly as designed.
```

All three scenarios behaved exactly as designed. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.

## Risk Notes Carried Forward From the Launch Package

- Fail-closed was Mike's explicit choice; every currently-known raise-exposed caller (`archive_detail()`, `archive_list()`, `archive_view()`) was updated in this same change, not left as a follow-on — matching Phase 2's "close the gap in the same PR" precedent.
- `list_contracts()`'s inclusion (Section 5 above) is a real, intentional scope extension beyond the approved package's literal wording, made because leaving it out would have shipped an inconsistent half-fix on the identical file type the package was already protecting. Flagged here for visibility, not smuggled in silently.

---

*End of PHASE3_ARCHIVE_WALKTHROUGH_REPORT_v1.*
