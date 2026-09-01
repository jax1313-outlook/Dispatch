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

Six sections, in the operator's order:

```
MISSION SOURCE     customer, their contact, their phone
LOAD CONTROL       load number (theirs, optional), service type, rate
PICKUP             facility, appointment, contact, phone, access
DELIVERY           facility, appointment, contact, phone, access,
                   additional stops
CARGO              description, pallets, pieces, weight
NOTES              anything else that matters on this run
```

**Use the existing Mission Record data structure.** Do not create a second mission structure.
Do not invent a courier structure or a medical structure. The Mission Record remains
authoritative; the template populates it.

### Multi-stop work

Additional stops are one per line, pipe separated, inside the DELIVERY section:

```
Additional stops: Publix DC Lakeland | 2026-09-02 14:00 | Dock 7 | 863-555-0114
                  Winn-Dixie Orlando | 2026-09-02 17:00 | Dock 2 | 407-555-0198
```

They become the `stops` list the Driver Cockpit already reads, so a phoned-in three-stop run
renders exactly like a swept one. Blank means one delivery, which is the common case and is
not an error.

*This format is an engineering choice, not doctrine — it keeps multi-stop capture inside the
one template and inside a plain-text email a driver can finish with one thumb. Worth
revisiting after real use.*

---

## Where it lives

| | |
|---|---|
| `dispatch/load_number.py` | assignment, generation, the COMI prefix rule |
| `dispatch/mission_template.py` | the one template, both intake methods |
| `tests/test_load_number_doctrine.py` | no orphans, exact storage, COMI recognition |
| `tests/test_mission_intake.py` | equivalence: every source, one record |
