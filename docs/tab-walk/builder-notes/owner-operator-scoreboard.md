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
and five to build. **Goals are the new concept.** Everything else is arithmetic
over data Dispatch already holds. A goal is a number Mike sets and the system
remembers, so it needs a home. Settings is the obvious one, beside the stall
thresholds, which are the existing precedent for an operator-set number.

## Accounting is architecturally present — CORRECTION 2026-09-09

An earlier version of this note said no accounting system exists. That was
wrong, and wrong in a way that mattered: it confused a missing implementation
with a missing architecture.

The correct finding, per Mike:

| Layer | State |
| --- | --- |
| Accounting role and handoff | Defined in Dispatch architecture and workflow |
| Accounting interface boundary | Defined. Accounting is one of eight connectors, alongside email transport, load board, mapping, scanner and Outlook |
| Accounting implementation | Replaceable. QuickBooks is one candidate, not the definition |
| Live accounting adapter | Not proven in the repository |

The handoff already exists and is honest about itself. `accounting_export.py`
writes one JSON file per settlement into an export directory, and the accounting
connector labels that result `MANUAL` rather than letting a written file read as
money having moved. That is a destination, not a gap.

Two things the connector will not do whatever provider is chosen: write a
settlement, invoice or payment, and decide what is owed. Both are Dispatch's own
record and its own authority.

So the boundary is: Dispatch prepares and routes the accounting handoff.
External accounting software owns bookkeeping, invoicing, payments, collections,
disputes, profit reporting and the accounting record. Billing and Profitability
are parked because they duplicate the external wheel, not because the work has
nowhere to go.

**Preserve, do not absorb.** Existing accounting-facing data, export logic,
notification types, APIs and handoff structures stay for later adapter work.

### What that leaves to decide

Four of the eleven notification types are accounting events: invoice created,
payment received, payment overdue, settlement disputed. Two of the eleven Alerts
sources are as well: disputed settlements under Decisions Required, overdue ones
under Exceptions. These are accounting-facing structures, so under the preserve
rule they stay. Whether they should surface on Dispatch's screens before a live
adapter exists is a separate question and is open.

## The scorecard is not accounting

Its purpose is operational decision support. It answers two questions:

> Do I need another load this week?
> Should I use Thursday, Friday, or reserve capacity to close the goal gap?

It does not replace accounting software and does not claim accounting-grade
profit. The gross target, if defined later, is operational.

## Open questions

1. Where does a goal live, and is it one number or one per week and month?
2. Is the trend a comparison of two windows, or a direction on a series?
3. The four accounting notifications and two Alerts sources are preserved under
   the boundary rule. Should they still surface on Dispatch screens before a
   live adapter exists?
4. Gross profit estimate is marked optional. Build it or not?

## Answer

Not yet answered.
