# Tab Walk

The single entry point for the tab-by-tab walk of the portal. Every note and
finding from the walk lives under this directory and nowhere else.

Start here. If a tab-walk note is not linked from the table below, it does not
exist as far as the after-build process is concerned.

## The lens

Tabs are read through the worker constitution architecture, at
`docs/architecture/DISPATCH_WORKER_CONSTITUTION_ARCHITECTURE.md`. Every tab
answers the same six questions before its findings are written.

[LENS.md](LENS.md) holds those questions, what counts as a lens finding, and the
vocabulary questions that are still open between the constitution and existing
doctrine. Read it once before tab 01 and do not re-argue those questions per tab.

The objective is understanding before redesign. Working capability is preserved.
No broad refactor comes out of this walk. Findings only. Mike decides.

## How this is organised

One folder per tab. Each folder holds:

- `FINDINGS.md` — the whole tab in one file. Scope, what it should do, what it
  actually does, numbered findings, decisions, and what it hands to other tabs.
- `evidence/` — screenshots, captured responses, log excerpts. Referenced by
  filename from the findings above them.

`_template/FINDINGS.md` is the blank. Copy it if a new tab is added.

## Working rules

- One working copy at `D:\Dispatch`. The walk does not get its own clone and
  does not get its own repository. Three copies once cost seven hours of
  silent HTTP 500s.
- Notes are committed on the `docs/tab-walk` branch and pushed after each tab
  is finished. That push is the backup. There is no second place to look.
- Code fixes go on their own branch, one per tab, never on this branch. A bad
  fix must not be able to take the notes with it.
- A finding is not closed because the code changed. It is closed when the
  `Proven` line carries a date and a real load run on Mike's laptop.

## Finding IDs

Format is `PREFIX-NNN`, for example `LOADS-004`. The prefix per tab is in the
table below and at the top of each `FINDINGS.md`.

Numbers are permanent. Never renumber, never reuse. A commit message, a test
name, or a later report may point at `BILLING-002` months from now, and it has
to still mean the same thing.

## Severity

| Severity | Means |
| --- | --- |
| blocker | Joe cannot run a load through this tab at all |
| broken | The feature errors or returns wrong data |
| wrong | It works but the behavior is not what dispatch needs |
| rough | Correct but slow, confusing, or takes too many steps |
| cosmetic | Presentation only |

## Tabs

Nav entries below are the 24 on `main`, confirmed against the running portal at
`127.0.0.1:8080` on 2026-09-09. The joe-portal branch adds JOE Portal,
Candidates, Booking and New Mission. Those are not in the running nav, so they
are listed as templates under tab 02 rather than as nav entries.

| # | Tab | Prefix | Nav entries | Status |
| --- | --- | --- | --- | --- |
| 01 | [Dispatch](01-dispatch/FINDINGS.md) | DISPATCH | Dispatch, Operations, Calendar, Exceptions | findings open (code side) |
| 02 | [Pre-Commitment Lifecycle](02-pre-commit/FINDINGS.md) | PRECOMMIT | Load Search, SAM, Pipeline | not started |
| 03 | [Fleet](03-fleet/FINDINGS.md) | FLEET | Fleet | not started |
| 04 | [Drivers](04-drivers/FINDINGS.md) | DRIVERS | Driver Pay | not started |
| 05 | [Billing and Profitability](05-billing/FINDINGS.md) | BILLING | Billing, Profitability | not started |
| 06 | [IFTA and Fuel](06-ifta/FINDINGS.md) | IFTA | IFTA, Fuel Estimator | not started |
| 07 | [Compliance](07-compliance/FINDINGS.md) | COMPLIANCE | Compliance | not started |
| 08 | [Brokers and Outbound](08-brokers/FINDINGS.md) | BROKERS | Brokers, Publisher, Email Templates | not started |
| 09 | [Intelligence and Library](09-intelligence/FINDINGS.md) | INTEL | Intelligence, Library | not started |
| 10 | [Archive and Queues](10-archive/FINDINGS.md) | ARCHIVE | Archive, Queues, Conflict Notices | not started |
| 11 | [Portal Shell and Settings](11-portal-shell/FINDINGS.md) | SHELL | Home, Settings | not started |
| 12 | [Driver Facing](12-driver-facing/FINDINGS.md) | DRIVERFACE | none in main nav; reached directly | not started |

Status values, in order: `not started`, `walked`, `findings open`, `fixed`,
`proven`. A tab reaches `proven` only when every finding in it is closed
against a real load on Mike's laptop.

## Where other things belong

- Behavior decisions go in `DECISION_LOG.md` at the repo root. Record only the
  decision ID here.
- Architecture and conformance reports stay where they are at the repo root.
  Do not add new top-level reports for the walk.
