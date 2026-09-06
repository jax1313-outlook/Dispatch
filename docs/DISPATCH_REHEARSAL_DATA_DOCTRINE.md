# DISPATCH REHEARSAL DATA DOCTRINE

**Status:** Doctrine · **Authority:** Mike Zachary · **Stated 2026-09-06**

---

## THE FIVE RULES, AS MIKE STATED THEM

> **REHEARSAL DATA**
>
> 1. Must be tagged at creation.
> 2. Must be visibly marked wherever displayed.
> 3. Must never be represented as live operational truth.
> 4. Must not silently contaminate live financial reporting.
> 5. May be viewed through an intentional rehearsal mode or filter.

**Rules 1–4 are requirements. Rule 5 is a permission** — a filter *may* exist. Its absence is not a
violation; its silent application would be, because Mike ruled on 2026-09-06 that the screens
**show both with rehearsal records marked.**

---

## THIS CONFIRMS DOCTRINE THAT ALREADY EXISTED

`dispatch/rehearsal.py` cites **Operational Readiness Mission Section 4.2**:

> *"No rehearsal record may ever display as an unlabeled live mission; rehearsal records must be
> excludable."*

That is rules 2 and 3, written before Mike stated them. **The mechanisms were built to it.** What
the audit below shows is that the mechanisms were built and then not called.

---

## COMPLIANCE AUDIT — 2026-09-06

| Rule | State | Evidence |
|---|---|---|
| **1. Tagged at creation** | **PARTIAL — the switch is off** | `tag_if_active()` is called from the `dispatch.store` create functions for all five record types, so a record created while a session is active *cannot* be untagged. But `DISPATCH_REHEARSAL_SESSION` reports `UNCONFIGURED` and `DISPATCH_MODE` is unset, so **nothing tags itself today** |
| **2. Visibly marked wherever displayed** | **7 of 20 screens** — `rate_confirmation_print` fixed 2026-09-06 | See the table below |
| **3. Never represented as live operational truth** | **NOT MET** | Follows from rule 2. On 14 screens a rehearsal load renders identically to real freight |
| **4. Must not silently contaminate financial reporting** | **PARTIAL** | Home now states it. `billing`, `profitability`, `ifta`, `driver_pay`, `fuel_estimator` compute over mixed data and say nothing |
| **5. May be viewed through a mode or filter** | **Permitted, partly built** | `banner_context()` drives a full-width banner on every page while a session runs. `purge_session()` exists and **nothing calls it** — deliberately, because Section 8 item 9 makes running one Mike's decision. No *display* filter exists, and none was asked for |

### Rule 2, screen by screen

**MARKED — calls `rehearsal_badge()`**

`dispatch` · `dispatch_detail` · `driver_home` · `home` · `load_readonly_detail` · `stakeholder_view`

**UNMARKED — renders load records with no rehearsal label**

`archive` · `billing` · `brief` · `calendar` · `dispatch_decision` · `driver_detail` ·
`driver_pay` · `equipment_detail` · `exceptions` · `fleet` · `ifta` · `profitability` ·
`search`

**`rate_confirmation_print` was fixed first, 2026-09-06** — the only screen in that list whose
output leaves the building. It is now marked in four places, because a reader who misses one may
still act on the page:

- **The `<title>`**, which becomes the filename when printed to PDF. A `Rate Confirmation.pdf` in
  someone's downloads folder was the failure worth preventing.
- **A bordered banner above the document**, naming the session.
- **A diagonal watermark** across the page.
- **A refusal at the signature block** — *"VOID — NOT FOR SIGNATURE. A signature on this page binds
  no one."* The signature lines are left visible, because Mike ruled *show both, marked*, not hide.
  That is where a page stops being information and becomes an agreement.

The terms paragraph asserts that an agreement exists; on a rehearsal page that sentence is answered
where it is printed rather than only at the top.

**Built for paper, not for a screen.** Heavy borders and near-black text so it survives a grayscale
print and a photocopy, with `print-color-adjust: exact` so the browser cannot strip the marking on
the way to the printer. A watermark that vanishes on paper is worse than none, because the screen
looked marked. Ten tests, including one asserting the marking appears inside the `@media print`
block, and three asserting **no marking of any kind** reaches a live document.

---

## THE MECHANISMS THAT ALREADY EXIST

**Do not build new ones. Call these.**

| Mechanism | What it does | Where |
|---|---|---|
| `rehearsal.tag_if_active(table, id)` | Tags on write. No-op when no session is active, so the operational path is unchanged | `dispatch/rehearsal.py` |
| `rehearsal.label_for(record)` | Returns `"REHEARSAL"` or `""`. **One answer to "is this labelled", not re-derived in nine places** | `dispatch/rehearsal.py` |
| **`rehearsal_badge(record)`** | **Template global, available in every template already.** Per-record badge, reads the stored column | `portal/app.py` |
| `rehearsal_active` / `rehearsal_label` | Context processor — the per-session banner in `base.html`, on every page | `portal/app.py` |
| `services.rehearsal_share()` | Counts for aggregates. **Counts, never filters** | `dispatch/services.py` |
| `rehearsal.purge_session()` | Removes one session's records and nothing else. Refuses without `confirm=True` | `dispatch/rehearsal.py` |

**A badge is for a row. A total cannot wear one** — so an aggregate screen must say it in words.
That is what `rehearsal_share()` is for, and why Home's note is separate from the badge.

**Two banner classes, two meanings, do not merge them:**

- `.rehearsal-banner` — *a session is running right now.* `base.html`, red, full width.
- `.rehearsal-data-note` — *what is on this screen includes rehearsal records.* True long after the
  session ended. Amber.

**Amber, not red, for the data note.** A rehearsal record is not an error, and a red badge on
legitimate test data teaches the eye to ignore red.

---

## WHAT THIS MEANS FOR THE TAB WALK

**Every tab session checks its own screen against rules 2, 3 and 4 and fixes what it finds.**
Fourteen screens are unmarked; each belongs to a tab that will be walked. Adding
`{{ rehearsal_badge(record) }}` beside a load id is a one-line change and needs no new machinery.

**Before PILOT-01, rule 1 needs the switch thrown.** Until `DISPATCH_REHEARSAL_SESSION` is set for
test work, new test records will be created untagged and the retroactive tagging of 2026-09-06 will
have to be repeated.

---

## HISTORY

- **2026-09-06** — Mike states the five rules. Two test loads and one milestone tagged retroactively
  to session `REH-20260906-1568E597` (closed `ABANDONED`; no rehearsal was ever run under it).
  Home marked: badge on rows, worded note on aggregates. Audit above recorded.
- **Earlier** — Section 4.2 mechanisms built: tagging in the write path, `label_for`,
  `rehearsal_badge`, the session banner, `purge_session`. Called by six screens.
