# STAGE6_ARCHIVE_REVIEW_QUEUE_WALKTHROUGH_REPORT_v1

## Archive Review Queue v1 -- age-based, portal/models/archive.py only

**Status:** Implemented and verified. Branch: `stage6-archive-review-queue` (based on `stage12-manager-foundation`).

**Responds to:** Mike's "Approve Stage 6 build," followed by review and approval of `DISPATCH_STAGE6_ARCHIVE_BUILD_DESIGN_v1.md` ("Approve design").

---

## What Changed

1. **`portal/models/archive.py`** — every new record now carries `review_status` (`"pending"` default), `reviewed_at`, `reviewed_by`, `disposition_reason`. New `list_review_queue(age_days=180)` returns pending records older than the threshold, oldest first. New `mark_reviewed(record_id, section, disposition, reason, reviewed_by)` records a Keep/Delete decision — refuses a second decision on an already-reviewed record (`ValueError`), matching this codebase's existing refuse-resubmission convention (`IFTAReportApproval`'s `AlreadySubmittedError`). "Deleted" never removes the record or its evidence — only the disposition is recorded.
2. **`portal/routes/api.py`** — new `POST /api/archive/review-decision`, gated with `@authority_required` (the same decorator `/settings` uses). Records the decision through the Spine's existing, unmodified `create_approval_event()`/`create_work_item()`, with the acting user's real `session_id`/`user_id`/`role` — the first Portal action route in this codebase to populate those fields with live identity rather than leaving them nullable.
3. **`portal/routes/pages.py`** — `/archive` now also computes and passes the Review Queue.
4. **`portal/templates/archive.html`** — new Review Queue panel with Keep/Delete buttons, reusing existing table/button CSS classes.
5. **`portal/templates/base.html`** — new `archiveReviewDecision()` JS function, matching the existing `resolveConflict()`/`archiveEntry()` pattern.
6. **`tests/test_archive_review_queue.py`** (new) — 21 tests.

## A Real Bug Found and Fixed Before This Count, Not an Implementation Detail

The build design assumed an `ApprovalEvent` could exist without a Work Item (`work_item_id=""`). It cannot: `approval_events.work_item_id` is `TEXT NOT NULL REFERENCES work_items(work_item_id)` — an enforced foreign key, confirmed by a `sqlite3.IntegrityError` the first time the route was actually exercised. Fixed by creating a minimal Work Item (`source_type="archive_review"`) before recording the approval — the exact same "create a Work Item, then record the Spine action against it" pattern `dispatch/manager/staff_report.py` already uses, not a new one invented for this build. Flagged here rather than silently patched around.

## What Did Not Change

`cin_lite/archive.py`, the IFTA compliance archive, `dispatch/spine/`, and `dispatch/security/` are untouched — the Spine's `create_approval_event()`/`create_work_item()` and Security's `authority_required` are consumed, not modified. Every other Portal page and route (`/manager`, `/settings`, `/home`) behaves exactly as before. The IFTA-to-generic-Approval-Event-schema migration remains entirely deferred, per the approved design's explicit scoping.

## Automated Test Results

- New tests in isolation: `python3 -m pytest -q tests/test_archive_review_queue.py` — **21 passed, 0 failed.**
- Full suite: `python3 -m pytest -q` from the repo root — **2,473 tests, 0 failures, 0 errors** (2,452 from before this build + 21 new).
- Structural guard confirms `portal/models/archive.py` contains no `unlink`/`rmtree`/`os.remove` call anywhere.

## Live Walkthrough

Run against a live Flask dev server (`python -m portal.app`, throwaway temp data directories) on `127.0.0.1:8095`.

```
GET /archive (empty state) -> 200, no Review Queue panel

-- seed one archive record, backdated 200 days --
GET /archive -> 200, "Archive Review Queue (1)" panel renders correctly,
  Keep/Delete buttons present

-- authorization boundary --
POST /api/archive/review-decision (unauthenticated) -> 302 Location: /login?next=...

-- create an Authority user, log in --
POST /api/archive/review-decision (Authority, disposition=deleted) -> 200
  {
    "approval_event_id": "APV-...", "work_item_id": "WI-...",
    "record": {"review_status": "deleted", "reviewed_by": "USER-...", ...}
  }

-- direct verification --
Record still physically present in portal/models/archive.py's JSON store,
  only review_status changed to "deleted"
list_review_queue() now returns [] (correctly excluded once reviewed)
ApprovalEvent: action=APPROVE_ARCHIVE_DELETE, session_id and user_id both
  populated, role=Authority, audit_id present

-- repeat decision on the same record --
POST /api/archive/review-decision (same record, disposition=kept) -> 409
  "Archive record ARC-LOA-0001 already reviewed (status='deleted')"

-- unaffected surfaces --
GET /manager   -> 200
GET /settings (no session) -> 302 Location: /login?next=/settings
```

The dev server was stopped and its throwaway data directories removed after the walkthrough; no repository files or production data were touched by it.

## Risk Notes Carried Forward

- **No physical purge mechanism exists.** "Delete" is a recorded decision only. Building an actual file/record removal capability is real, separate, and more dangerous scope — deliberately not part of this build, per the approved design.
- **Age-based, not version-based.** The literal "Current + 3 Previous" trigger from `ARCHIVE_REVIEW_POLICY.md` §2 still can't be built until Stage 8 (Version Doctrine on Archive) exists. 180 days is a documented, tunable default, not doctrine.
- **Scoped to `portal/models/archive.py` only.** `cin_lite/archive.py` and the IFTA compliance archive each still have their own separate, unreviewed retention gap — unifying all three under one Review Queue remains a future, separately-scoped decision.
- **Manager's M5 Archive half is not wired to this queue yet.** This build unblocks it directly, but consuming it from `dispatch/manager/` is its own follow-on task, not bundled here.

---

*End of STAGE6_ARCHIVE_REVIEW_QUEUE_WALKTHROUGH_REPORT_v1.*
