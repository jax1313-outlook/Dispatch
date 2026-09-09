# Parking Lot

Things removed or deferred during the tab walk that still need a decision. This
is not a backlog and not a build list. Nothing here is scheduled. It is the
record of what was set aside so that it is set aside deliberately rather than
lost.

An item leaves this file when Mike decides where it goes, or decides it goes
nowhere. Record that decision here with a date before deleting the entry.

**When Mike says delete, he means park.** Removing something from a screen
during the walk never removes the capability. It comes off the screen and it
comes in here. The same holds for a function that loses its last caller: record
it, park it, keep walking. Nothing is destroyed during the tab walk.

## Removed from Home, 2026-09-09

Home was stripped to Screened Loads, Active Loads, the sample-data banner and
the two card sections. Everything below came off it. None of the capability
underneath was touched.

Every row below is parked, not closed. Off the Home screen, capability intact,
revisit before the build list is finalized.

| Removed from Home | Still lives at | Note |
| --- | --- | --- |
| Conflict Notices count | Conflict Notices tab | Mike said it is of no value to him on Home. Whether it earns space anywhere is open. |
| Publisher Queue count | Publisher tab | |
| Archived Records count | Archive tab | |
| Intelligence Records count | Intelligence tab | |
| Fleet Active, drivers and equipment | Fleet tab | |
| Pending Decisions count | Pipeline tab | Mike named Pipeline as where it belongs. |
| Stalled Loads badge, table and notify button | Dispatch tab, which already carried a stalled badge and a Send Stall Alerts button | The Dispatch button has its own defect. See DISPATCH-006. |
| Financial Snapshot and Run Aging Check | Billing tab and Dispatch tab, both of which already render the same figures and the same button | Three screens showing one set of numbers is unresolved. See below. |

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

## SAM, parked entire — 2026-09-09

Mike's ruling: **SAM is divorced from Dispatch completely.** It has its own
GitHub repository and will be developed as a separate program later. Every
builder note and every function surrounding SAM is parked.

Nothing is removed yet. Parked means out of scope for the walk and recorded
here, per the standing rule.

**Tab 02 no longer covers SAM.** It is Load Search and Pipeline only. The
opportunity-card placement note no longer waits on a SAM review.

### What "SAM" actually reaches

This is larger than the SAM tab. Surveyed on `main`, 2026-09-09.

| Surface | What it is |
| --- | --- |
| SAM tab | `/sam`, `sam.html`, the nav entry, `helpers.load_and_process_sam` |
| SAM card | `_card_sam.html`, both densities, and the Home top-opportunities strip |
| `cin_lite/` | The contract-intelligence engine. Acquisition, four agents (extractor, router, summarizer, proposal writer), eight govcon rule modules, the proposal workflow, pipeline, pending, archive, control |
| Pipeline tab | Fed by `cin_lite.pending` |
| Queues tab | Fed by `cin_lite.pipeline.routing_history` |
| Alerts feed | Three of eleven sources are contract-side: govcon pending, review queue, analysis queue |
| Brief page | Renders SAM entries as well as freight entries |
| Sandbox | `source_type == "sam"` entries share one store with freight entries |

### The one real entanglement

`cin_lite/email_delivery.py` is not a SAM file. It is the shared outbound mail
transport, and `dispatch/notifications.py` imports it for all eleven freight
notifications. Every load alert in Dispatch goes out through the
contract-intelligence module.

So separating SAM is not removing a tab. The freight side currently depends on
a module inside the thing being separated. That transport has to move to the
Dispatch side, or be duplicated, before SAM can leave. This is the first item on
any SAM separation work, and it connects directly to the alerting build item
below.

### Open question for Mike

Does SAM come off the running portal now, or stay visible until the separate
program exists? Parking the notes is unambiguous. Removing the tab, the card,
the Pipeline and Queues surfaces, and three of the eleven Alerts sources is a
much larger change and has not been directed.

## Build items, designed but not built

These are decided. They are not tab-walk edits and nothing here is implemented
during the walk. They go on the build list when the walk is finished.

**Alerting: record, deliver, track.** Decided by Mike 2026-09-09. Full evidence
and the decisions are in
`builder-notes/alerts-detection-generation-delivery-tracking.md`.

Three pieces, in order:

1. **An alert record, created when the condition is detected.** Alert ID, alert
   type, related mission record, trigger time, intended recipient, and the four
   status fields for created, attempted, succeeded and failed. Nothing today
   records that an alert exists.
2. **Automatic firing for stalled loads.** Stalled is the only one of the eleven
   notification types that waits on a human pressing a button, which means it
   depends on the same person who has not noticed the stall. The other ten
   already fire from inside the service layer.
3. **Result recording, and an outbox drain.** The outbox is required, not a
   failure. Creation and delivery are separate events. The transport already
   returns a result string carrying most of the delivery answer and it is thrown
   away at the last step. Recording it is the smallest first move. Draining the
   outbox when connectivity returns is deterministic chassis work under R5.

## Related

Questions that need answering before any of the above becomes a build item go
in `builder-notes/`, not here. This file tracks what was set aside. That folder
tracks what is not yet understood.

## SAM removal, what actually happened — 2026-09-09

Mike's ruling: remove the SAM tab and card only. Everything else stays until the
mail transport is rehomed.

Removed from the screens:

- The SAM nav entry in `base.html`
- The Home top-opportunities strip, and the SAM card import with it
- `sam_cards` and the SAM half of `screened_count` in the Home route. Screened
  Loads counts freight only now, which is what the name meant

Left alone, and reachable:

- `/sam` still resolves and `sam.html` still renders
- `_card_sam.html` still works, both densities
- `cin_lite` entire, Pipeline, Queues, the Brief page, and the three contract
  sources in the Alerts feed

Restoring the tab is one line in `base.html`. Restoring the Home strip is a few
more. Nothing was destroyed, per the standing rule.

The blocker on going further is unchanged: `dispatch/notifications.py` gets its
mail transport from `cin_lite/email_delivery.py`, so all eleven freight
notifications run through the module being separated. That moves first.

## SAM retention manifest — what moves to the SAM repository

Mike's instruction: retain every SAM function and capability, parked here for
movement to the SAM GitHub repository later. Nothing below is deleted. This is
the packing list.

State described is `tab-walk/build` as of 2026-09-09, after the mail transport
was rehomed.

### The engine — `cin_lite/`

The contract-intelligence package, twenty-eight modules.

| Group | Modules |
| --- | --- |
| Intake and processing | `acquisition`, `processing`, `run` |
| Agents | `extractor`, `router`, `summarizer`, `proposal_writer` |
| Rules, ten of them | `set_aside`, `naics_sin`, `cyber_compliance`, `foreign_influence`, `jv_mp_structure`, `past_performance`, `subcontractor_dominance`, `vendor_network`, `pricing_anomaly`, `base` |
| Control and flow | `control`, `pipeline`, `pending` |
| Storage | `archive` |
| Workflows | `proposal` |
| Contract mail | `email_delivery`, now decision rendering and routing only |
| Fixtures | `sample_data/` |

### Portal surfaces

- `/sam` route in `portal/routes/pages.py`, and `sam.html`
- `_card_sam.html`, both densities
- `portal/routes/decisions.py` — the emailed decision link handler
- `portal/routes/pipeline.py` — Pipeline and Queues
- `pending.html`, and the contract half of `archive.html` and `brief.html`
- `helpers.load_and_process_sam` in `portal/helpers.py`
- The three contract sources in the Alerts feed: govcon pending, review queue,
  analysis queue

### Configuration and data

- `DISPATCH_SAM_API_KEY`, `DISPATCH_SAM_LIMIT`, `DISPATCH_SAM_POSTED_FROM`,
  `DISPATCH_SAM_POSTED_TO`, `DISPATCH_SAM_NAICS`, `DISPATCH_SAM_PTYPE`,
  `DISPATCH_SAM_FETCH_DESCRIPTION`, `DISPATCH_ARCHIVE_PATH`
- The contract archive on disk, `D:\Archive\CIN`, including its own outbox

### Tests that go with it

`test_acquisition`, `test_processing`, `test_rules`, `test_routing`,
`test_summarization`, `test_extraction`, `test_run`, `test_control_center`,
`test_control_email`, `test_email_control`, `test_pipeline_api`,
`test_proposal_trigger`, `test_archive`, `test_storage_routing`.

`conftest.py` is shared and stays. It carries SAM fixtures the contract tests
need, so the SAM repo takes a copy of those fixtures rather than the file.

### Already resolved

**The mail transport.** Was `cin_lite/email_delivery.py`, now `dispatch/mail.py`.
Dispatch owns addressing, message building, the HMAC token pair, SMTP and the
outbox. The two programs no longer share an outbox. `cin_lite` imports the
transport from Dispatch until it leaves, then takes a copy. Done 2026-09-09.

### Still crossing the line

Two things still reach across. Two more did and are resolved.

**Receipt vision. RESOLVED 2026-09-09.** Moved to `dispatch/receipt_vision.py`.
It was freight work all along: fuel-receipt scanning in the driver portal and
the dispatch API. It sat in the contract package only because that is where it
was first written, the same shape as the mail transport, and it moved the same
way. The contract agents package now holds only the extractor, router,
summarizer and proposal writer.

**Backup.** `dispatch/backup.py` imports `cin_lite.archive` deliberately, as a
module attribute, so it covers both archives. After the split it covers one.

**The sandbox store.** Freight and contract entries share one store, separated
only by `source_type`. Splitting the programs splits that store.

## Fleet, folded into Settings — 2026-09-09

Not parked, moved. Recorded here because the nav lost an entry and someone will
look for it.

The roster lives at the top of the Settings page now: drivers, equipment,
assignments, Add Driver, Add Equipment, the filters and the inline edits. All of
it, unchanged. `/fleet` redirects to `/settings`, and the driver and equipment
detail pages kept their paths because Load Search links into them.

Nothing about Fleet was removed or reduced. See `03-fleet/FINDINGS.md`.

## TOOLBOX — 2026-09-09

Mike's ruling. TOOLBOX is not workflow. It is not Dispatch. It is not operations
review. It is a collection of owner/operator calculators, references, links and
utility tools, and it does not exist yet.

Future shape:

```
TOOLBOX
 ├── Calculators
 ├── Reference Tables
 ├── Federal Links
 └── Owner/Operator Utilities
```

Named for it: Fuel Estimator, Per Diem Calculator, Fuel Surcharge Calculator,
Fuel Surcharge Tables, and related utility tools. Capability is not deleted.

### What actually exists, of the five named

| Named | Class | Where it is |
| --- | --- | --- |
| Fuel Estimator | Proven | A working screen. Parked off the nav 2026-09-09; `/fuel-estimator` still resolves |
| Fuel Surcharge Tables | Proven, as data not as a screen | The IFTA jurisdiction table in `dispatch/models.py` carries a rate and a surcharge for every state. It renders inside IFTA reports, never as a reference table |
| Per Diem Calculator | Missing | The phrase does not appear anywhere in the repository |
| Fuel Surcharge Calculator | Missing | Surcharge is applied inside IFTA reporting. Nothing calculates one standalone |
| Cost Per Mile, Breakeven | Missing | Mike listed both as future |

So TOOLBOX is one existing screen, one existing table that has never been
presented as a table, and three things to build.

### The Fuel Estimator, recorded

**Calculations.** Estimated fuel cost from distance, MPG and price per gallon,
via `GET/POST /api/dispatch/fuel-estimate`. A quick-reference grid built in the
page: eight distances from 100 to 2000 miles against 6, 7 and 8 MPG, priced at
the current average.

**Reference data and where it comes from.** Two defaults are pre-filled from
real IFTA data, not typed in. Average fuel price is total fuel spend divided by
total gallons across every IFTA fuel purchase. Fleet MPG is total trip-leg miles
divided by total gallons. With no IFTA data, both return zero and the fields
read "N/A", which is what Mike's screen shows today.

**Dependencies.** `get_avg_fuel_price` and `get_fleet_mpg` in
`dispatch/services.py`, both reading IFTA tables. The optional Load ID field
auto-fills distance from a rate confirmation.

### One thing to settle before TOOLBOX is built

The Fuel Estimator has an **Add as Expense** button. It posts a fuel expense
onto a load. That is a write into a live record, which is workflow by Mike's own
definition, sitting inside a calculator.

It cannot move to TOOLBOX unchanged without carrying workflow into a screen
defined as not being workflow. Three options, Mike's call: the button stays
behind on a workflow screen, TOOLBOX gets a narrow exception for it, or the
estimator splits into a pure calculator plus a separate action.

Note also that TOOLBOX's reference data is IFTA-derived. A calculator screen
that reads live operational data is not quite a standalone utility either.

### TOOLBOX ruling — 2026-09-09

Mike settled the blocker. **TOOLBOX is read-only utility functionality.**

Kept in the Fuel Estimator, all unchanged: the calculation, the MPG defaults,
the fuel price defaults, the quick reference table, and the IFTA-derived
pre-fill.

**Removed: Add as Fuel Expense.** It posted a fuel expense onto a live load. A
workflow action modifying an operational record does not belong in a calculator.
The button and its handler are gone from the page. The expense API is untouched
and every workflow screen that uses it still does.

**Also removed: the Load ID field.** Mike, same day. It only read a rate
confirmation to fill in distance, but it still tied a calculator to a specific
operational record. The page now knows nothing about loads. The estimator API
still accepts a load_id and is still tested; only this screen stopped sending
one.

Future TOOLBOX: Fuel Estimator, Per Diem Calculator, Fuel Surcharge Reference,
Fuel Surcharge Calculator, Federal Reference Links, and further owner/operator
utilities.

**Parked, not built: apply an estimate to a load.** Mike's answer to the open
question is that this becomes a separate workflow action on a workflow screen.
TOOLBOX is not responsible for modifying live records. Where that action lives
is not decided, and the natural candidates are the load detail screen and
Billing. Until it exists, a fuel estimate is copied by hand into an expense.

## Five screens parked — 2026-09-09

Mike walked Profitability, Compliance, Brokers, Publisher and Library and parked
all five. Off the nav, routes intact, nothing removed underneath. Nav went from
twenty-four entries to sixteen.

Checked before removing, the same discipline that caught the Fleet problem: none
of the five is linked from any other page. Their only internal links are their
own filter forms. The Alerts feed reaches Publisher and Library by path and
still works.

| Parked | What it holds | Note |
| --- | --- | --- |
| Profitability | Per-load rankings by profit, with sort, order, status and date filters, plus profitable and unprofitable counts | Overlaps Billing. Both read the same rate and expense data |
| Compliance | Document tracker with expiry alerts, entity/type/status filters, Add Document and Check Alerts | Empty today. Its expiry alerts already reach the Alerts feed |
| Brokers | Contact directory and performance scorecard, with active and blacklisted counts | Mike: useful inside the Publisher workflow, not as a tab of its own |
| Publisher | The action queue. Broker Packet Required and the rest, with their manifests and Generate Draft | See below |
| Library | Company, broker and customer libraries of approved reusable assets | Mike: useful inside the workflow, not beside it |

### Two things worth flagging

**Publisher is a constitutional worker.** The constitution gives Publisher the
commitment package lifecycle and its own boundary: may produce, may not commit.
Parking the screen parks a view, not the role. Publisher still runs, still
raises actions, and those actions still appear in the Alerts feed under
Decisions Required. Nothing about the worker changed.

**Brokers and Library are the Publisher's inputs.** The Publisher queue's own
manifest names what it is missing: W-9, insurance, authority, business card,
rate sheets, terms, capabilities, compliance documents, fleet and equipment,
driver qualifications. Those live in the Library. The broker it is packaging
for lives in the broker directory. So all three parked screens are pieces of one
workflow, which is consistent with Mike's note that Brokers and Library belong
inside the workflow rather than beside it.

That makes the future shape a question worth asking once rather than three
times: does the Publisher workflow absorb the broker directory and the Library
as panels, the way Settings absorbed Fleet? Not decided.
