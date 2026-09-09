# The Owner/Operator Scoreboard

- Opened: 2026-09-09, by Mike, during the Billing walk
- Clarified: 2026-09-09. Supersedes the earlier note framed around Billing metrics
- Status: OPEN — target state set, almost none of it built

## The ruling

**Billing and Profitability are not surviving because of accounting.**
QuickBooks or a future accounting integration already owns accounting. The only
functionality worth preserving from either screen is operational decision
support.

Both screens are parked. What survives is a new thing.

### Target state

| Metric | |
| --- | --- |
| Weekly revenue | |
| Weekly goal | |
| Revenue gap | goal against actual |
| Monthly revenue | |
| Monthly goal | |
| Revenue trend | up or down |
| Gross profit estimate | optional |

Purpose: support freight decisions. Not accounting decisions.

### Out of scope for Dispatch entirely

Invoicing, payments, collections, factoring, disputes, accounting reports, and
historical profitability reports. These belong to accounting systems.

## What exists today

Checked on `tab-walk/build`, 2026-09-09.

| Wanted | Class | Notes |
| --- | --- | --- |
| Weekly revenue | Missing | Nothing computes a week |
| Monthly revenue | Implemented but unverified | Exists as a chart series only, and nothing renders it |
| Revenue trend | Missing | No rolling window, no prior-period comparison anywhere |
| Weekly and monthly goals | Missing | There is no concept of a goal in the repository. No field, no setting, no store |
| Revenue gap | Missing | Follows from goals |
| Gross profit estimate | Partially proven | Revenue minus all expenses, all-time. Fuel is one of eleven expense categories |
| Maintenance escrow | Missing | The word appears nowhere. `repair` is money already spent, not money set aside |

So the scoreboard is one number that exists, one that exists in the wrong shape,
and five to build.

**Goals are the new concept.** Everything else is arithmetic over data Dispatch
already holds. A goal is a number Mike sets and the system remembers, which
means it needs somewhere to live. Settings is the obvious home, next to the
stall thresholds, which are the existing precedent for an operator-set number.

## What the accounting boundary costs

Drawing the line at accounting has consequences beyond two screens. Recorded so
they are decided rather than discovered.

**Four of the eleven notification types are accounting events.** Invoice
created, payment received, payment overdue, settlement disputed. If accounting
leaves Dispatch, those leave with it or they fire on records Dispatch no longer
owns.

**Two of the eleven Alerts sources are accounting events.** Disputed
settlements sit in Decisions Required and overdue settlements in Exceptions. A
dispute is a collections matter by this ruling, so it is questionable whether
either belongs on the Alerts screen.

**The accounting connector is documented as not built.** `accounting_export.py`
and the accounting connector both record that no QuickBooks integration exists
anywhere in the codebase, and Settings tells the operator the same. So the
system Mike is deferring to does not exist yet either. Until it does, parking
invoicing means the work is done outside Dispatch by hand.

## Open questions

1. Where does a goal live, and is it one number or one per week and month?
2. Is the trend a comparison of two windows, or a direction on a series?
3. Do the four accounting notifications and two Alerts sources go with
   accounting, or stay until the integration is real?
4. Gross profit estimate is marked optional. Build it or not?

## Answer

Not yet answered.
