# MISSION INTAKE ARCHITECTURE

Status: **LOCKED DISCOVERY.** Issued by the operator, 1 September 2026.

---

## The assumption that broke

Dispatch assumed Mission Records originate primarily from SWEEP. **That assumption is no
longer valid.** Work arrives seven ways:

| Source | |
|---|---|
| `SWEEP` | found by the opportunity sweep |
| `EMAIL` | completed template returned to `Ops@l1truck.com` |
| `JOE` | taken down by voice, JOE acting as intake clerk |
| `CUSTOMER` | direct customer |
| `PHONE` | phone call |
| `COURIER` | courier and medical routes |
| `API` | future machine intake |

**The Mission Record does not care where the work originated.** All sources converge into the
same record and the same workflow.

## The locked discovery

```
ONE MISSION TEMPLATE
MULTIPLE INTAKE METHODS
ONE MISSION RECORD
ONE WORKFLOW
```

No courier template. No medical template. No truckload template. No specialty templates.
**One Mission Template, populated by different people and systems.**

Service type is a *field*, not a template. That is the whole difference between one system
and seven.

## Load Number doctrine

> **Every Mission Record MUST have a Load Number. No exceptions.**

Because it is the retrieval key for all of: mission retrieval, archive retrieval, library
retrieval, document linkage, communication linkage, COMI processing.

**No orphan Mission Records permitted.** A record without a number exists and cannot be found
again.

### Assignment

**If a broker, customer or shipper provides a number — use theirs, stored exactly.**

```
847261        CVS-44912        ABC123
```

No case folding, no stripping dashes, no tidying. A number we cleaned up no longer matches
theirs on an invoice.

**If no external number exists — Dispatch creates one.**

```
L1-0001    L1-0002    L1-0003        (format configurable)
```

> The generated number is **NOT** pretending to be a broker number. It is a legitimate
> Dispatch Load Number.

The record carries `load_number_origin` as `SUPPLIED` or `GENERATED`, because *did they give
us this number or did we* decides who it can be quoted to. A generated number never lands in
`card_data.load_id` — that field is the broker's own reference, and our number sitting in it
is how a payment goes missing.

### What this corrected

The first implementation made the broker's load number a **required** field. A direct
customer, a phone call and a courier run all arrive without anyone else's number, so that
version refused exactly the work this doctrine exists to accept.

## The number comes first

JOE assigns the Load Number **when the driver asks for the template**, not when it comes
back. That ordering is what makes the email path work at all.

```
Driver:  "Joe, email me a Mission Template."

JOE assigns          L1-XXXX
JOE emails           To: Ops@l1truck.com
                     Subject: L1-XXXX
                     Body: Mission Template

Driver completes and replies — subject unchanged
```

### COMI processing rule

> If an inbound subject begins with `L1-`, treat the message as **MISSION INTAKE**.

Not a general communication. Not a broker message. Not a customer message. The prefix is the
entire rule, which is why `dispatch/load_number.py:is_mission_intake` is tight about it and
the tests check what it must *reject* as carefully as what it accepts.

## The two workflows

```
EMAIL                          JOE (voice)

Email                          "Joe, open a Mission Template."
  ↓                              ↓
Email Helper                   JOE assigns L1-XXXX
  ↓                              ↓
COMI                           JOE walks the template field by field
  ↓                              ↓
Mission Intake                 COMI
  ↓                              ↓
Scheduler                      Scheduler
  ↓                              ↓
Mission Record                 Mission Record
  ↓                              ↓
Calendar Entry                 Calendar Entry
  ↓                              ↓
Normal Dispatch Workflow       Normal Dispatch Workflow
```

**JOE is a clerk and commits nothing.** It issues a number, reads the template, takes the
answers down and hands them over.

## The template

**The one-page layout, ruled 2026-09-15** (Owner: *"go ahead with the one page template"*),
**extended to thirty-one fields on 2026-09-16** when one card per delivery gave DELIVERY its
own Consignee and BOL number. Seven sections, in the operator's order. The New Mission screen
and the Mission Brief are the same document and both render exactly this;
`dispatch/mission_template.py` is the definition and `tests/test_mission_template_published.py`
holds it to this list.

```
IDENTITY           Load Number · Mission Number (assigned by Dispatch) ·
                   Service Type (LTL / Courier)
MISSION SOURCE     Customer / Shipper / Broker · their contact · their phone · their email
LOAD CONTROL       Load control (Customer / Level 1) · rate · rate agreed with ·
                   payment type · paid by · amount
PICKUP             facility and address · appointment · contact · phone ·
                   access instructions · SPECIAL INSTRUCTIONS
DELIVERY           Consignee · BOL number · facility and address · appointment ·
                   contact · phone · access instructions · SPECIAL INSTRUCTIONS
CARGO              description · pieces / pallets · weight (lbs, total)
NOTES              anything else that matters on this run
```

Removed by that ruling: Status, Intake and Taken by from the brief; the separate "load number
(theirs)"; load control name, role, phone and email; Shipper at pickup; Stop 1 load control and
the per-stop load control lines; Cargo items; separate Pallets and Pieces. **Older records keep
every stored value; a removed field is simply not shown.**

**Use the existing Mission Record data structure.** Do not create a second mission structure.
Do not invent a courier structure or a medical structure. The Mission Record remains
authoritative; the template populates it.

### One card per delivery

**Ruled by the Owner, 2026-09-15.** Stops are no longer entered. There is no "additional
stops" line in the template, on the New Mission screen, or in the emailed template.

> *"One card pre load mission."*
>
> *"rain stops one stop from completing so the driver returns with one load still onboard.
> This is why each must stand alone totally. the only binding item is the shipper. Everything
> thing else stands alone."*

Three pallets for three dealerships are three cards. Each carries its own consignee, BOL
number, delivery address, appointment, freight, signed POD, invoice and load number, and each
is committed, delivered, invoiced, paid, rolled or discarded without touching the others —
*"2 out of three get paid that day."*

**Capturing them.** "ANOTHER DELIVERY FOR THIS SHIPPER" — a submit button on the New Mission
screen, a link on a saved brief — files the card in hand and opens the next one carrying the
shipper and the pickup only (`mission_template.SHIPPER_KEYS`). Consignee, BOL, delivery,
freight, rate and notes start blank. Three deliveries phoned in at one sitting are typed
once each, not once plus two edits.

**The only tie is a label.** `dispatch/shipper_group.py` tags the cards with the first card's
load number and renders "1 of 3" on the card, the brief and the cockpit banner. It binds
nothing — *"The '1 of 3' label on each card that is enough! not more!"*

**A roll is not a new card.** A delivery pushed to another day is the same card with a new
appointment, still OPEN: *"a new appointment for one that rolls to the next day, is still the
same pallet, still going to the same location and it is still the <OPEN LOAD.> using the same
everything except a different day. Which may be a week later."*

**Older records are untouched.** A record captured before this ruling keeps its stored `stops`
list and the Driver Cockpit still renders it. Nothing is deleted or rewritten; the entry
concept is gone, the stored data is not.

*Cargo and the Load Diagram in `DRIVER_COCKPIT_LOCKED_DIRECTION.md` still read by stop, which
is deliberate: they describe what is physically on the truck for inspection, which can be
freight for several cards at once.*

---

## Where it lives

| | |
|---|---|
| `dispatch/load_number.py` | assignment, generation, the COMI prefix rule |
| `dispatch/mission_template.py` | the one template, both intake methods; `SHIPPER_KEYS` |
| `dispatch/shipper_group.py` | the "1 of 3" label, and nothing else |
| `tests/test_load_number_doctrine.py` | no orphans, exact storage, COMI recognition |
| `tests/test_mission_intake.py` | equivalence: every source, one record |
