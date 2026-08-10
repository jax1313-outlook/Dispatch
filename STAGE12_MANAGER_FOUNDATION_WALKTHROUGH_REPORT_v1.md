# STAGE12_MANAGER_FOUNDATION_WALKTHROUGH_REPORT_v1

## Manager -- Staff Report Generator (Phase M2 + M3, read-only)

**Status:** Implemented and verified. Branch: `stage12-manager-foundation` (based on `stage7-security-foundation`).

**Responds to:** Mike's "Approve Stage 12 build," followed by review and approval of `DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md` ("Approve design").

---

## What Changed

1. **`dispatch/manager/`** (new package: `signals.py`, `classify.py`, `priority.py`, `staff_report.py`) — a read-only Staff Report generator. Reads five already-existing, already-tested signal sources; classifies each per `MANAGER.md` §7's nine-class taxonomy; ranks by the nine-tier priority framework from `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md` §8; for anything clearing the Review Needed bar (card_level ≥ 2), creates a Work Item and Portal Card through the Spine's own, unmodified machinery.
2. **`portal/routes/manager.py`** (new) — `manager_bp`, one route: `GET /manager`. No POST/PATCH/DELETE anywhere on the blueprint.
3. **`portal/templates/manager.html`** (new) — renders the Staff Report's classification-count summary and the ranked, currently-active card list, reusing Stage 5's `.card-level` CSS classes.
4. **`portal/routes/__init__.py`** — registers `manager_bp`.
5. **`portal/templates/base.html`** — one new nav link, styled identically to every existing entry.
6. **`tests/test_manager_foundation.py`** (new) — 30 tests.

**Zero new database tables. Zero Spine schema changes.** Every Work Item this build creates moves through an already-approved, already-allowed transition path — `CREATED → VALIDATION_PENDING → VALIDATED → PORTAL_CARD_PENDING → PORTAL_CARD_CREATED` — unchanged since Stage 4. `ROUTED_TO_MANAGER` remains exactly as it was: a dead end, untouched.

## What Did Not Change

`dispatch/notifications.py`, `dispatch/services.py`, `portal/models/sandbox.py`, `portal/models/conflict.py`, `dispatch/spine/`, `dispatch/security/`, and every existing route and template are unmodified — all six signal-source functions this build calls are read, never altered. `/settings` remains gated exactly as Stage 7 left it. The three existing HMAC email-decision gates and the phone-approval workflow are untouched.

## Two Implementation-Time Findings, Flagged Not Silent

1. **The build design listed `dispatch.services.check_overdue_settlements()` as a read-only signal source. It is not.** Calling it marks settlements overdue in the database and sends an email via `notifications.notify_payment_overdue()` as a side effect — that scan already runs elsewhere in the Portal (the existing "Run Aging Check" button). Manager instead reads the *result* of that scan via `dispatch.services.list_settlements(payment_status="overdue")`, a genuine read. A structural guard test (`test_check_overdue_settlements_never_called_directly`) confirms `signals.py` never calls the mutating function.
2. **A live-walkthrough-only defect, found and fixed during this stage, not left for a future pass.** The first working version of `generate_staff_report()` returned only cards *newly materialized in that exact request* as `"cards"`. Combined with dedup (correctly preventing re-creation of an already-tracked Work Item), this meant a genuinely unresolved item silently vanished from `/manager` after its first view — dedup was suppressing the *display*, not just the *duplicate write*. Confirmed live: a critical Conflict Notice appeared on the first page load and was gone on the second, despite being fully unresolved. Fixed by separating the two concerns: `generate_staff_report()` still materializes at most one Work Item/Card per signal ever (dedup unchanged, confirmed by `list_work_items()` count staying flat across passes), but the page now displays **every currently-active card at or above the review bar** (`_active_cards()`, reading `list_portal_cards()` fresh each request), not just the ones created in that specific pass. Re-verified live after the fix: the same four cards remained visible across three consecutive page loads, with `list_work_items()`/`list_portal_cards()` staying at exactly 4 the whole time — no duplicates, no disappearing cards.

## Scoping Notes (Flagged, Not Silent)

- **No enrichment of existing Work Items.** If the underlying signal for an already-materialized card changes (e.g., a stalled load gets even more stalled), this build does not update the existing card — it stays as first classified. Re-classifying a stale card is additive future scope, explicitly out of scope per the design's §10.
- **No action capability on `/manager`.** View-only — no approve/dismiss/promote/route button. Adding one is Portal-Wide Enforcement-adjacent territory (would need session/role awareness) and was explicitly excluded from this build.
- **IFTA suspect entries assigned Tier 1** (safety/security/legal/compliance/authority) in `priority.py`, on the reasoning that an uncorrected low-confidence fuel-purchase extraction risks an inaccurate government filing. This is a documented, correctable default, not doctrine — flagged the same way `classify.py`'s severity thresholds are flagged.
- **Per-signal-type classification thresholds** (e.g., "2x the stall threshold is Decision Needed, not just Status"; "7+ days overdue is Decision Needed") are this build's own tunable defaults. The nine-class taxonomy and its card-level mapping are doctrine; which numeric threshold separates two classes for a specific signal type is implementation judgment, documented inline in `classify.py` and `priority.py`.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_manager_foundation.py` — **30 passed, 0 failed.**
- Full suite: `python3 -m pytest -q` from the repo root — **2,432 tests, 0 failures, 0 errors** (2,402 from before Stage 12 + 30 new).
- Structural guard tests confirm: no direct `work_items.current_state` write anywhere in `dispatch/manager/` (only `apply_transition()`); no call to any `dispatch.security.auth` write function; no call to any approval/booking/submission function; the `/manager` route declares no `methods=` argument (GET-only by Flask default).

## Live Walkthrough

Run against a live Flask dev server (`python -m portal.app`, `PORTAL_DATA_DIR`/`DISPATCH_OPERATIONS_ROOT` pointed at a throwaway temp directory — never real production data) on `127.0.0.1:8092`.

```
GET  /home                          -> 200 (unaffected)
GET  /manager  (empty state)        -> 200, "Nothing needs your attention right now."
GET  /settings (no session)         -> 302 Location: /login?next=/settings (Stage 7 untouched)

-- seeded one representative signal per source --
Stalled load, 60h in 'created' (2.5x the 24h threshold)  -> Decision Needed, L3, Tier 3
Overdue settlement, 3 days overdue (< 7 day bar)         -> Status, L1 (no card)
Open exception, severity=critical                        -> Conflict, L4, Tier 1
Conflict Notice, severity=critical                        -> Conflict, L4, Tier 1
IFTA fuel purchase, extraction_confidence=0.3             -> Review Needed, L2, Tier 1

GET /manager -> 200
  Summary: Conflict: 2, Review Needed: 1, Decision Needed: 1, Status: 1
  Cards Needing Attention (4), ranked:
    1. Exception: other           (L4, Tier 1)
    2. Conflict Notice: missing_rate (L4, Tier 1)
    3. Suspect IFTA fuel purchase  (L2, Tier 1 -- ranks above the Tier 3 item despite lower card_level)
    4. Stalled load                (L3, Tier 3)
  -> confirms "Tier always wins over card_level" ranking rule
  -> the Status-level overdue settlement appears ONLY in the summary count, never as a card
  -> every card carries "This is a recommendation only. No action is authorized. Mike decides."

Re-fetched /manager three consecutive times: all four cards remained visible each time
  (the fix described above, confirmed live, not just in tests)
DB check: work_items = 4, portal_cards = 4, unchanged across all three fetches -- dedup holds,
  nothing duplicated, nothing silently dropped

Direct DB inspection: every created work item's current_state == "PORTAL_CARD_CREATED";
  none ever touched ROUTED_TO_MANAGER
```

The dev server was stopped and its throwaway data directory removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **No re-classification of stale cards.** A card reflects its signal's state at the moment it was first materialized; if the underlying situation changes (worsens or resolves outside Manager's own visibility), the card doesn't update itself. Flagged above, not hidden.
- **No cross-repo Stage Gate awareness yet.** Phase M4 (tracking Claude-3's `DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md`) needs a read mechanism between the two repositories that doesn't exist yet — out of scope for this build, per the design.
- **Security and Archive/IFTA dedicated monitors (Phases M5–M6) are separate, not-yet-approved future builds.** This build's IFTA coverage is limited to reading suspect entries as one signal source among five, not a dedicated compliance monitor.
- **The `ROUTED_TO_MANAGER` dead-end state remains unresolved**, exactly as `DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md` found it. This build didn't need it and didn't touch it; it would still need its own design pass if some future function wants to explicitly hand a Work Item to Manager rather than Manager originating its own.

---

*End of STAGE12_MANAGER_FOUNDATION_WALKTHROUGH_REPORT_v1.*
