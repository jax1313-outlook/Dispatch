# STAGE12_MANAGER_ARCHIVE_WIRING_WALKTHROUGH_REPORT_v1

## Manager -- Archive Review Queue wiring (completes Phase M5)

**Status:** Implemented and verified. Branch: `stage12-manager-archive-wiring` (based on `stage6-archive-review-queue`).

**Responds to:** "Wire Manager to the new Archive Review Queue," followed by review and approval of `DISPATCH_STAGE12_MANAGER_ARCHIVE_WIRING_DESIGN_v1.md` ("Approve design").

---

## What Changed

1. **`dispatch/manager/signals.py`** — new source type `ARCHIVE_REVIEW_ITEM`, reading `portal.models.archive.list_review_queue()` (Stage 6, unmodified) directly. Manager never calls `mark_reviewed()`.
2. **`dispatch/manager/classify.py`** — fixed `ARCHIVE`'s card level from 1 to 2 (see below); new classifier maps every Archive Review item uniformly to `ARCHIVE`, no age-based sub-tiering, matching the buildout design's single fixed card level for this card type. Summary text points explicitly to `/archive`.
3. **`dispatch/manager/priority.py`** — new tier mapping: Archive Review items are always Tier 7 ("Library, Archive, or cleanup work"), the exact tier the buildout design names for this category.
4. **`dispatch/manager/staff_report.py`** — unmodified, again. The eighth signal source in a row to flow through this pipeline with zero orchestrator changes.
5. **`tests/test_manager_foundation.py`** — 8 new tests.

## The Bug the Design Flagged, Confirmed and Fixed

`classify.py`'s `ARCHIVE` class had been mapped to card level 1 since the M2+M3 build, one below `REVIEW_BAR_CARD_LEVEL = 2`. It had never been reachable by any signal source, so it never mattered. Wiring in Archive Review items without the fix would have silently produced zero cards, ever — every Archive-classified signal would have been below the bar. Corrected to 2, matching `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md` §7's Portal Card Model table exactly. `test_archive_review_item_classifies_archive_and_clears_review_bar` is the direct regression test for this fix.

## What Did Not Change

`portal/models/archive.py`, `portal/routes/api.py`'s `/api/archive/review-decision`, and every other Stage 6/Stage 12 file remain untouched. Manager only reads `list_review_queue()`; the Keep/Delete decision stays exactly where Stage 6 put it — on the Authority-gated `/archive` page.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_manager_foundation.py` — **58 passed, 0 failed** (50 from the prior three build passes + 8 new).
- Full suite: `python3 -m pytest -q` from the repo root — **2,481 tests, 0 failures, 0 errors** (2,473 from before this build + 8 new).
- Structural guard confirms no call to `mark_reviewed(` anywhere in `dispatch/manager/`.

## Live Walkthrough

Run against a live Flask dev server on `127.0.0.1:8096`, using the real Stage 6 Archive Review Queue mechanics end to end.

```
-- seed one backdated (200-day) archive record --
GET /manager -> 200
  Card: "Archive Review: Walkthrough Manager Archive Record"
  Level 2, Priority Tier 7
  Summary: "In the Archive Review Queue, 200.0 days old. Review and
    record a Keep/Delete decision at /archive -- Manager does not
    action this itself."
  Closing sentence present.

-- dedup across two page loads --
GET /manager x2 -> still exactly 1 Archive Review card each time
DB check: exactly 1 archive_review_item Work Item, unchanged across fetches

-- resolve through the REAL /archive Keep/Delete route (Stage 6, untouched) --
Logged in as Authority, POST /api/archive/review-decision (disposition=kept)
  -> 200, record's review_status now "kept"

-- fresh Manager signal collection after resolution --
signals.collect_signals() -> 0 archive_review_item matches (correctly excluded)
GET /manager -> still shows the already-materialized card (the same
  accepted, documented limitation carried from every prior Manager
  pass -- "no enrichment of existing Work Items" -- not a new gap)

-- unaffected surfaces --
GET /home            -> 200
GET /settings (no session) -> 302 Location: /login?next=/settings
```

A stray, useful observation surfaced mid-walkthrough, flagged rather than silently left: the Stage Gate panel's mirror file (`docs/STAGE_STATUS.json`) still read *"Recommended next stage: 6 — ...unlocks...M5's Archive half..."* — accurate when written, now stale since Stage 6 shipped and this build closed that gap. Refreshing that file is part of this build's Claude-3 tracking update, not a code change.

The dev server was stopped and its throwaway data directories removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **No re-classification of stale cards** — same limitation as every other Manager signal source. A resolved Archive item's card doesn't disappear or update; that remains future enrichment scope, not part of this build.
- **Per-item, not aggregated** — if the Archive Review Queue grows large, this produces one card per item (all Tier 7, ranked below anything more urgent). Flagged in the design as a real tradeoff, not attempted to be solved here.
- **The `docs/STAGE_STATUS.json` mirror needs a manual refresh** to reflect that Stage 6 has shipped and this wiring is complete — the same manual discipline the M4 design always assumed, exercised here for the first time since that build shipped.

---

*End of STAGE12_MANAGER_ARCHIVE_WIRING_WALKTHROUGH_REPORT_v1.*
