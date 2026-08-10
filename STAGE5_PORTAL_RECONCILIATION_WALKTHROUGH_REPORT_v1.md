# STAGE5_PORTAL_RECONCILIATION_WALKTHROUGH_REPORT_v1

## Card Level and Version Doctrine Display on Portal Cards

**Status:** Implemented and verified. Branch: `stage5-portal-reconciliation` (based on `stage4-spine-schemas`).

**Responds to:** Mike's approval ("Approve Stage 5") of the Migration Plan's Stage 5 (Portal Reconciliation), applying the recommended default for the stage's open question (card_level auto-derived from status/score, with an explicit Manager/Mike override that sticks).

---

## What Changed

1. **`portal/models/sandbox.py`** — `card_level` (0–5), auto-derived from `status` via `_derive_card_level()`, with a high-value-score override (score ≥ 90 on an OPEN/INTERESTED/PURSUE/WATCH entry bumps to Decision level 3, so a genuinely high-value opportunity doesn't get lost among ordinary Review-level cards). `set_card_level()`/`clear_card_level_override()` give Manager/Mike an explicit override that subsequent status changes will not silently overwrite. `version` + `last_change` fields, bumped only when `_detect_change_label()` finds a real change (rate, schedule, score direction, summary, routing recommendation, flags, or a catch-all) — a same-data refresh (the common case when `/sam` or `/dispatch` re-runs acquisition) does **not** bump the version, per Version Doctrine's explicit "not for meaningless system noise" rule. `update_status`, `update_scoring`, `set_inquiry_draft`, `link_engine_load`, and `update_engine_status` each bump version with a plain-language label when they represent a real change. `get()`/`get_all()` backfill `version`/`card_level`/`last_change` defaults at read time for entries written before this change.
2. **`portal/models/conflict.py`** — `card_level` derived from `severity` + `human_decision_required` (`critical` → 4, matching the doctrine's own "Conflict" level name), stored on `create_notice()` and backfilled at read time for legacy notices.
3. **Templates** (`home.html` ×2 card loops, `sam.html`, `dispatch.html`, `brief.html`, `conflicts.html`) — render the card-level badge, `Ver: X`, and `Last Change:` alongside the existing status tag.
4. **`portal/static/style.css`** — new `.card-level`/`.card-level-0`…`.card-level-5`/`.card-version`/`.card-last-change` classes.
5. **`tests/test_version_doctrine.py`** (new) — 21 tests.

## What Did Not Change

No route signatures, no JSON API response shapes beyond the new dict keys already present on `sandbox`/`conflict` records, no change to `card_visual()`'s existing score-threshold labeling (kept as-is, extended alongside rather than replaced), no change to `dispatch/spine/` (Stage 4's work is untouched by this stage). `portal/models/library.py`, `publisher.py`, `archive.py`, `intelligence.py` — out of scope for Stage 5, untouched.

## Scoping Note (Flagged, Not Silent)

The Stage 5 launch package calls for "allow Manager/Mike override" as part of card_level. `set_card_level()`/`clear_card_level_override()` implement that capability at the model layer and are directly tested, but no dedicated Portal UI control (button, form) was built for it in this stage. Building one now would mean building a Mike-facing governance control surface twice — once here, once properly at Stage 10 (Alert Governance Retrofit), which explicitly calls for "one shared control surface... rather than building the same governance UI four separate times." The capability exists and is ready for Stage 10 to wire a control onto.

## Automated Test Results

Full suite: `python -m pytest -q` from the repo root — **all tests pass, 2,373 tests, 0 failures, 0 errors** (2,352 from before Stage 5 + 21 new in `tests/test_version_doctrine.py`, confirming zero regression against Stage 4's baseline).

## Live Walkthrough

Run against a live Flask dev server (`python portal/app.py`, `PORTAL_DATA_DIR` pointed at a throwaway temp directory — never real production data) on `127.0.0.1:8199`.

```
1. Created a fresh high-value opportunity (score 97, OPEN status):
   SBX-DISPATCH-WALK-001   Ver: 1   Last Change: Created   card_level: 3
   (card_level 3, not the OPEN-status default of 2 -- the high-value-score
   override fired correctly)

2. Re-ran create_entry with a revised rate (2400 -> 2650), same score:
   Ver: 2   Last Change: Rate Updated
   (version bumped exactly once, labeled correctly -- not "Details Updated",
   because the rate-specific check in _detect_change_label() fired first)

3. Created a critical conflict notice against that entry:
   card_level: 4

GET /home
  -> 200, page contains "Ver: 2", "Last Change: Rate Updated", "card-level-3"

GET /conflicts
  -> 200, page contains "card-level-4" for the critical notice

GET /brief/SBX-DISPATCH-WALK-001
  -> 200, page contains "Level 3", "Ver: 2", "Last Change: Rate Updated"

GET /sam, /dispatch
  -> 200 (both render without error; no entries created in this walkthrough
     for these sources, but template rendering paths are shared and covered
     by tests/test_version_doctrine.py's assertions)
```

All scenarios behaved exactly as designed, including the two things this design specifically checked for: a same-data refresh does not create version noise (verified directly in the test suite, not just by omission in this walkthrough), and the high-value-score override correctly promotes an otherwise-Review-level OPEN card to Decision level without requiring a status change. The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files were touched by it.

## Risk Notes Carried Forward

- **`_detect_change_label()`'s field list is deliberately targeted, not exhaustive.** It checks rate, schedule, score, summary, routing recommendation, and flags explicitly, then falls back to a generic "Details Updated" for any other `card_data` difference. This means every real change is still caught (nothing is silently dropped — the catch-all guarantees that), but the *label* may sometimes be the less-specific "Details Updated" rather than a more precise one. Expanding the specific-label list is a low-risk, purely additive follow-up if Mike wants sharper labels for other fields.
- **The card_level override UI gap is real** until Stage 10 lands — Mike cannot currently click a button to override a card's level; the capability exists only at the model/test layer. Flagged above, not hidden.
- **High-value-score threshold (90) reuses `helpers.SCORE_HIGH_THRESHOLD`'s value but is hardcoded separately** in `sandbox.py` as `_HIGH_VALUE_SCORE_THRESHOLD` rather than importing it, to avoid a new cross-module coupling between `portal.models.sandbox` and `portal.helpers` for a single constant. If the threshold ever changes, both locations need updating — low risk given how rarely this threshold changes, but worth noting.

---

*End of STAGE5_PORTAL_RECONCILIATION_WALKTHROUGH_REPORT_v1.*
