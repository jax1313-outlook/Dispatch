# Parking Lot

Things removed or deferred during the tab walk that still need a decision. This
is not a backlog and not a build list. Nothing here is scheduled. It is the
record of what was set aside so that it is set aside deliberately rather than
lost.

An item leaves this file when Mike decides where it goes, or decides it goes
nowhere. Record that decision here with a date before deleting the entry.

## Removed from Home, 2026-09-09

Home was stripped to Screened Loads, Active Loads, the sample-data banner and
the two card sections. Everything below came off it. None of the capability
underneath was touched.

| Removed | Still lives at | Needs a decision? |
| --- | --- | --- |
| Conflict Notices count | Conflict Notices tab | No. Mike said it is of no value to him. |
| Publisher Queue count | Publisher tab | No. |
| Archived Records count | Archive tab | No. |
| Intelligence Records count | Intelligence tab | No. |
| Fleet Active, drivers and equipment | Fleet tab | No. |
| Pending Decisions count | Pipeline tab | No. Mike said Pipeline is where it belongs. |
| Stalled Loads badge, table and notify button | Dispatch tab, which already carried a stalled badge and a Send Stall Alerts button | No. |
| Financial Snapshot and Run Aging Check | Billing tab and Dispatch tab, both of which already render the same figures and the same button | Partly. Three screens showing one set of numbers is unresolved. See below. |

## Open items

**Attention Needed Across Departments.** A composed feed of publisher actions,
pipeline items and review-queue items. It existed only on Home, under a
documented consolidation scope. It is now on no screen at all, and
`helpers.attention_needed` has no caller. Two questions. Does the composition
belong on some other surface, and does R4 change what it should be called now
that departments are superseded by agents.

**Load Overview charts.** Loads by Status and Monthly Revenue. The data is
untouched and still served by the chart API, but nothing renders it. Decide
whether these belong on a tab or nowhere.

**Recent Activity.** A fifteen-item milestone feed across all loads. It existed
only on Home. `get_recent_activity` in the dispatch store now has no caller in
the portal. Decide whether a cross-load activity feed belongs anywhere.

**Who owns the money figures.** The financial dashboard renders on Billing and
on Dispatch, and did on Home. One set of numbers on three screens, with no
answer yet to which worker owns them. Raised as DISPATCH-005 on tab 01.

**The orphaned notify helper.** `notifyStalled` is defined in the shared script
in `base.html`. Its only caller was the Home button. Dispatch uses a different
function, `sendStallAlerts`. Nothing calls `notifyStalled` now. Delete it or
give it a caller, but not before the alert question below is settled.

## Related

Questions that need answering before any of the above becomes a build item go
in `builder-notes/`, not here. This file tracks what was set aside. That folder
tracks what is not yet understood.
