# DRIVER COCKPIT — LOCKED DIRECTION

Status: LOCKED. Issued by the operator, 1 September 2026, after live review of the running
screen.

**Do not reintroduce dashboard concepts. Do not redesign. Refine the existing cockpit.**

---

## 1. What is built and holding

Verified against the running code, not asserted:

| | |
|---|---|
| Stop selector as primary navigation | built |
| `[PICKUP] [DELIVERY]` mode bar | built |
| Detail drawers carrying execution information | built |
| Cargo, truck-wide by stop | built |
| Load Arrangement, separate from Cargo | built |
| Load diagram: occupied, empty, stop ownership | built |
| ARRIVE auto-sending, BCC `Ops@l1truck.com` | built |
| Arrival notice generation | built |
| Checklists at READY / COMPLETE only | built |
| Manual mission creation, email and voice | built — see §8 |

## 2. Stop selector

```
[ STOP 1 ] [ STOP 2 ] ...
```

**The primary operational navigation mechanism.** Selecting a stop changes delivery details,
contacts, appointment times, access instructions, facility-map target and stop-specific cargo
visibility — **without creating another screen.**

**Preferred over PREVIOUS STOP / NEXT STOP**, which were removed.

> **Mission advancement and stop viewing are separate concepts.**

That distinction is the reason the buttons went. Advancing a mission is an act with
consequences; looking at another stop is not, and one control doing both would make every
glance a commitment.

## 3. Modes

```
[PICKUP] [DELIVERY]
```

These represent **work being performed** — loading, or unloading — which a driver understands
immediately.

### CURRENT is under review, and is not to be rebuilt

CURRENT was removed, restored as a transit panel, and withdrawn again after live review.

**The stop selector substantially reduced the need for it.** No further CURRENT redesign
until operational testing says otherwise: the question is whether a driver misses it in a
cab, and that cannot be answered from a chair.

The transit panel exists in history and can be recovered in one command if real use asks for
it.

## 4. Detail cards are execution cards

Both drawers contain, in this order:

```
LOAD NUMBER (bold)
Address
POC
Phone
Appointment
Access Instructions
Items
```

**The load number leads because it often functions as the facility access code.** Load
number, pickup number, reference number — the gate asks for it before it asks anything else.

Delivery follows the selected stop and shows a stop tag. Pickup does not move: there is one
pickup.

## 5. Ownership of information

**Broker belongs exclusively in BROKER** — name, contact, phone, reference number. Not on the
stop card, not in cargo. Two names on one screen means working out which is current.

*(The arrival notice names the broker because it is addressed to them. That is not a
duplicate identity.)*

**Cargo is everything on the vehicle, organised by stop.**

```
CARGO
  Stop 1   Aircraft Parts        2 pallets
  Stop 2   Airframe Fasteners    2 pallets
  TOTAL    4 pallets · 4 pieces · 8400 lbs
```

It serves driver visibility, **agriculture inspection, security checkpoint inspection**,
customer visibility and driver reference. Those last ones are why it must be truck-wide: an
inspector asks what is on the truck, not what is for this stop.

**Load Arrangement is separate**, and holds load position, occupied positions, empty
positions and capacity.

**The Load Diagram is mission execution, not document workflow.** It is used while loading,
unloading, sequencing and managing capacity, and shows occupied positions, empty positions
and stop ownership:

```
Position 1 - Stop 1      Position 4 - Stop 2
Position 2 - Stop 1      Position 5 - EMPTY
Position 3 - Stop 2      Position 6 - EMPTY
```

## 6. ARRIVE, notices and checklists

**ARRIVE creates a documented arrival event** — date, time, GPS, facility, load number.
Publisher generates the Arrival Notice, COMI routes it, it **auto-sends**, blind-copied to
`Ops@l1truck.com`.

Its purpose is **on-time arrival evidence, independent of warehouse gate processes.** That
independence is the point: the truck's record of when it arrived does not depend on a gate
guard logging it.

Checklists have two statuses only: **READY** and **COMPLETE**.

## 7. The cockpit is not an alert system

```
Route Risk discovers  →  JOE communicates
```

JOE decides phrasing and severity from Route Risk findings. **The Driver Cockpit displays;
it does not alert.** A second alert system on the glass would compete with the one that can
speak, and a driver would learn to trust neither.

---

## 8. MANUAL MISSION CREATION — new, and not built

**The operator names this a major discovery.** Built 1 September 2026 in
`dispatch/mission_template.py`; the equivalence tests are in
`tests/test_mission_intake.py`.

Dispatch must support automatic **and** manual mission creation **using the same Mission
Template**.

### Method 1 — email

> *"Joe email me a Mission Template."*

Driver completes it. Sends to `Ops@l1truck.com` with a COMI trigger in the subject.

```
Email → Email Helper → COMI → Scheduler → Mission Record → Load Number
```

### Method 2 — voice

> *"Joe open a Mission Template."*

**JOE acts as clerk.** The driver completes the template verbally.

```
JOE → COMI → Scheduler → Mission Record → Load Number
```

### Load numbering does not change

Every Mission Record receives a Load Number **assigned by Dispatch exactly as it is for
SWEEP-created missions** — whatever the source: SWEEP, email, JOE, manual intake. Same
process, same workflow.

That is what stops manual intake becoming a second class of load with its own rules.

### The core discovery

```
ONE MISSION TEMPLATE
MULTIPLE INTAKE METHODS
ONE MISSION RECORD
ONE WORKFLOW
```

This is the Mission Record doctrine holding under pressure. A freight source that arrives by
telephone is still a mission, and the temptation with manual entry is always to build a
lighter path for it — which produces two kinds of load, two sets of rules, and a record that
means different things depending on how it got there.

**It also completes JOE's co-driver role.** Taking a load down while the driver talks is
clerk work: research, organise, record. It commits nothing, and a Load Number is assigned by
Dispatch rather than by JOE.

---

## 9. What this locks

Nothing above is a proposal. The screen is refined from here, not redesigned, and the next
open question is **operational testing** — whether a driver in a cab misses CURRENT, and
what manual intake actually needs to capture.
