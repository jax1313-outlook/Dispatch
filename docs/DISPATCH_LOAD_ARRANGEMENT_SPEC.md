# DISPATCH LOAD ARRANGEMENT SPEC

Status: SPECIFICATION. Not implemented. Derived from the operator's Load Arrangement Data
Model, 30 August 2026.

---

## 1. Why this exists

The evaluation engine cannot judge a load it cannot describe. Everything specified so far
assumed the simplest possible shape: one pickup, one delivery, one commodity, one rate.

**Real work is not that shape.** A cargo van running courier and expedite freight carries
multiple orders, stops at several facilities in a fixed order, and is paid partly in
accessorials that have nothing to do with miles.

This document defines the load. `DISPATCH_EVALUATION_ENGINE_SPEC.md` defines what the
engine does with it.

## 2. Structure

```
Load
├── header          trip level: asset, service type, lane, windows, distance
├── stops[]         ordered; each with type, location, window, dwell, priority
│   └── cargo[]     per stop: order, commodity, units, handling, compatibility
├── utilization     weight / cube / pallet, computed
└── pricing         linehaul + accessorials, revenue and cost metrics
```

One Load is one Mission Record. Stops and cargo are **inside** it, not beside it — the
one-record doctrine holds. See `DISPATCH_STATE_TRANSITION_RULES.md`.

## 3. Load header

| Field | Notes |
|---|---|
| `load_id` | The broker's number, preserved exactly. See dual numbering. |
| `mission_number` | Ours. Numeric, 4 digits max. |
| `asset_id` | Which vehicle in `fleet[]`. May be unset until evaluated. |
| `service_type` | `FTL` / `LTL` / `dedicated` / `multi_stop` / `milk_run` |
| `pickup_window` | earliest, latest |
| `delivery_window` | earliest, latest |
| `origin`, `destination` | city / state |
| `total_miles` | |
| `planned_drive_time` | |
| `hos_impact` | See §8 — depends on an unresolved regulatory question |

`service_type` is not cosmetic. `milk_run` and `multi_stop` change what "the pickup" and
"the delivery" mean — see §8.

## 4. Stops — ordered, and the order is data

| Field | Values |
|---|---|
| `stop_number` | 1, 2, 3 … — the sequence **is** the plan |
| `stop_type` | `pickup` / `delivery` / `live_load` / `drop_hook` |
| `facility` | name, city/state, facility code |
| `window` | earliest, latest; `appointment` or `fcfs` |
| `dwell_minutes` | planned time on site |
| `priority` | `critical` / `flexible` / `backhaul` / `filler` |

Two fields here carry more weight than they look:

- **`dwell_minutes`** is where a van operation loses its day. Six stops at 45 minutes each
  is 4.5 hours before a mile is driven. Revenue per mile cannot see this; revenue per hour
  can. See §7.
- **`priority`** is the operator's own classification, not the broker's. A `filler` stop
  that fits on the way is worth almost nothing to drop; a `critical` one cannot be moved.
  This is the field that makes a stop sequence negotiable or not.

## 5. Cargo, per stop

| Field | Notes |
|---|---|
| `order_id` | customer order, PO, BOL |
| `commodity` | description |
| `hazard_flag` | drives an endorsement blocking condition |
| `temp_control_flag` | drives an equipment blocking condition |
| `pallets`, `pieces`, `weight_lbs`, `cube_ft3` | the four unit measures |
| `stackable` | `yes` / `no` / `floor_load` |
| `special_equipment` | liftgate, pallet jack, straps |
| `compatibility` | commodities this may not travel with |

**`compatibility` and `stackable` are capacity facts, not paperwork.** Non-stackable
freight consumes a pallet position it does not fill, so a load can be pallet-out at half
its weight. An incompatible pair cannot share the van at all, whatever the arithmetic says.

## 6. Utilization — three ratios, one binding constraint

```
weight_utilization = total_weight ÷ vehicle.weight_limit_lbs
cube_utilization   = total_cube   ÷ vehicle.cube_capacity_ft3
pallet_utilization = total_pallets ÷ vehicle.pallet_positions
```

**The binding constraint is whichever reaches 1.0 first.** A load can be weight-out,
cube-out or pallet-out, and they are different situations calling for different decisions.

This resolves the operator's Full / Heavy / Mixed figures:

| Named load | Pallets | Implied per pallet | Total |
|---|---|---|---|
| Full | 6 | ~1,667 lb | 10,000 lb |
| Mixed | 5 | 2,000 lb | 10,000 lb |
| Heavy | 4 | 2,500 lb | 10,000 lb |

**The arithmetic is consistent:** all three land on the same ceiling, so these are not three
capacity rules — they are **one payload limit expressed at three pallet weights**, capped by
deck positions.

**CORRECTION, 30 August 2026.** An earlier draft recorded these as `CONFIRMED`
specifications. They are not. **The cargo van and trailer have not been purchased**, so:

```
payload_capacity_lbs   UNCONFIGURED     operator target 10,000
pallet_positions       UNCONFIGURED     operator target 6
cube_capacity_ft3      UNCONFIGURED     no target stated
length / width / height UNCONFIGURED
```

The figures above are the **operator's stated intent for a vehicle not yet owned**. They
inform planning conversations. They are **never inputs to a calculation** — see
`DISPATCH_POLICY_PROFILE_SPEC.md` §4.8a.

Full / Heavy / Mixed remain useful as **named presets** for fast entry — a way to classify
a load without weighing every pallet. They are a convenience over the model, not the model.

### Stop efficiency

```
loads_per_stop, revenue_per_stop, miles_per_stop
```

These describe how hard the day is, not how well the freight fits. They belong to
complexity and profitability rather than to capacity.

## 7. Pricing

| Group | Fields |
|---|---|
| **Linehaul** | flat rate or per-mile |
| **Accessorials** | detention, layover, TONU, lumper, liftgate, temp control |
| **Revenue** | per mile, **per hour**, per stop, per unit |
| **Cost** | per mile, per hour, per stop |

**Accessorials are not a rounding error in this business.** Detention on a multi-stop run
can exceed the linehaul. A load evaluated on linehaul alone is evaluated wrong, and every
current Dispatch money figure is linehaul-only.

**Revenue per hour is the metric that fits a van operation.** Rate-per-mile is a truckload
measure; it cannot see dwell. Two loads at $3.50/mile are not comparable when one has two
stops and the other has seven.

## 7a. The Capacity Plan and the Mission Record

**SUPERSEDED HERE.** The day/commitment model is now governed by
`DISPATCH_CAPACITY_PLAN_DOCTRINE.md`, issued by the operator on 30 August 2026. This
section states only what this document needs; the doctrine is authoritative.

```
Capacity Plan  (the vehicle day - execution planning)
├── Vehicle Day          ├── Route Sequence
├── Stop Sequence        └── Remaining Capacity
├── Capacity Allocation
        ▲
        │  Mission Records attach to Capacity Plans.
        │  Capacity Plans do not replace Mission Records.
        │
Mission Record  (the commitment - per broker, may span days)
```

The van's capacity may be filled by one broker or split six ways:

```
Pallet 1  Broker A        One Truck
Pallet 2  Broker B        One Route
Pallet 3  Broker C   ►    One Driver
Pallet 4  Broker D        One Capacity Plan
Pallet 5  Broker E
Pallet 6  Broker F
```

Ownership fragments; execution does not. **The Capacity Plan carries that unity** — the
driver sees one day, one route, one plan. **The Mission Record carries the commitment**,
durable, per broker, and able to span days: pickup Tuesday, delivery Thursday is a valid
Mission lifecycle.

An earlier draft of this section collapsed the two into a single record. That lost the
commitment's identity the moment freight moved to another day, which is exactly the case
the operator confirmed happens.

### Where the numbers live

The Mission Record carries our mission number **and** its broker's load number, preserved
exactly — dual numbering is unchanged. The Capacity Plan carries no broker's number,
because it belongs to no broker.

### Capacity Allocation

```
allocation
  allocation_id       durable, ours - survives moving to another day
  mission_ref         the commitment this serves
  pallets, weight, cube
  stops               which stops in the sequence serve it
  status              committed / delivered / rescheduled / failed
```

**CONFIRMED:** allocations move between days keeping their identity, and their history
remains traceable.

### Stakeholder visibility

Each stakeholder sees only **their** load number, documents, proof artifacts, tracking and
status. Six brokers may share a vehicle day; **none sees another's freight, rate, customer
or stops.** The Capacity Plan is the operator's view and never a stakeholder's.

### What binds where

| Capacity Plan | Mission Record |
|---|---|
| The vehicle, the driver, the day | The broker and their load number |
| Stop sequence and its order | What was promised, and when |
| Total weight / cube / pallet utilization | This freight's share |
| Return to home base | Invoicing and payment |
| The locked calendar | Documents and proof for that stakeholder |

**Capacity binds at the Capacity Plan**, because the van is one van. Two pallets are never
over capacity alone — only against what the day already holds. The question is not "does
this fit the van" but **"does this still fit Tuesday?"**

## 7b. The lifecycle of a day — CONFIRMED by the operator, 30 August 2026

```
OPEN  ──►  CLOSED  ──►  PROPOSED  ──►  LOCKED  ──►  IN PROGRESS  ──►  COMPLETE
                            ▲                             │
                            └──── exception: resequence ───┘
```

| State | Meaning | Who moves it |
|---|---|---|
| **OPEN** | Accepting allocations; capacity remains | ACCEPT LOAD adds to it |
| **CLOSED** | Capacity reached, or the operator closed the day | Capacity, or the operator |
| **PROPOSED** | The engine has reasoned a stop sequence | **The engine** |
| **LOCKED** | The human approved it. **The calendar is produced here.** | **The human** |
| **IN PROGRESS** | The driver is running it | The driver |
| **COMPLETE** | Every stop done | The driver |

### LOCK DAY is a third activation event

Dispatch has had two events that bring something into existence. There is now a third.

| Event | Creates | Reversible |
|---|---|---|
| START SWEEP | Opportunities | Yes |
| ACCEPT LOAD | An allocation — a commitment to a broker | **No** |
| **LOCK DAY** | **The locked sequence, and the calendar** | **Yes, by exception** |

**The sequence is proposed when the day closes on capacity, not before.** Proposing a route
for a half-full day wastes the operator's attention on a plan that will change with the
next accepted load.

**The engine reasons the sequence. The human locks it.** This is the recommendation
boundary doing exactly what it exists for — the engine may produce an order; it may not
commit one. The calendar is an artifact of the human's lock, not of the engine's proposal.

### Closing the day — CONFIRMED, 30 August 2026

**The normal close is physical.** Most days the driver closes the day when the truck is
parked: **the day closes by power down.** There is no button to remember, because the act
of arriving and shutting off already means the day is over.

**JOE is the dialog assistant until final arrival**, and **JOE may propose closing the
day.** Proposing is within its authority; it does not close anything.

| Who | May |
|---|---|
| **Capacity** | Close the day automatically when the van is full |
| **The driver** | Close it deliberately, or by powering down at final arrival |
| **JOE** | **Propose** a close. Never perform one. |

### Telling the end of a day from a stop for fuel

**CONFIRMED as a requirement, 30 August 2026.** A power-down is not always the end of a
day — the driver shuts off for fuel, for a break, at a dock. A day closed by mistake at
11am is worse than a question.

**The governing rule is asymmetric, because the costs are.** A close proposed too late
costs one prompt. A close applied too early ends the day while commitments are outstanding,
and recovering means reopening — which re-reasons the whole sequence. So:

> **Never close while any commitment is outstanding.**

#### Signals that a power-down is *not* the end of the day

Any one of these is sufficient, and each is deterministic:

| Signal | Why it settles the question |
|---|---|
| **Stops remain incomplete** | The plan is not finished. Nothing else needs checking. |
| **Position matches a planned stop** | This is the dock. It is a stop, and its dwell is already planned. |
| **Allocations remain undelivered** | A commitment is outstanding. |

#### Signals consistent with the end of the day

| State | Reading | Action |
|---|---|---|
| All stops complete **and** at or near home base | End of day, near-certain | Propose the close. One confirmation. |
| All stops complete, **away** from home base | Ambiguous — the driver may be repositioning home | **Ask.** Do not assume. |
| Stops remain, for any reason | Not the end of the day | **Say nothing.** It is a stop. |

The third row matters as much as the first. A system that asks *"are you done?"* at every
fuel stop is a system the driver learns to dismiss, and the one time it matters they will
dismiss that too. **Silence is the correct behaviour for an ordinary stop.**

#### Who asks

JOE is dialog assistant until final arrival, so JOE is where the question belongs. **JOE
asks; the driver answers; the driver closes.** JOE proposing a close is within its
authority. JOE closing a day is not.

#### When it cannot tell

**UNKNOWN applies here as everywhere: an unrecognised power-down is not an event.** No
close, no guess, no prompt. The day stays open, and the driver can close it deliberately
whenever they choose.

A day left open costs nothing — it is closed on the next power-down at home, or by hand.
A day closed wrongly costs a reopen and a re-reasoned sequence.

### Resequencing is an exception, and it has an owner

**CONFIRMED:** the **driver initiates** a resequencing event. **JOE arranges the exception
and presents alternative proposals or rerouting.** The human decides.

```
driver hits a closed dock  ─►  JOE proposes alternatives  ─►  human chooses  ─►  re-lock
```

JOE proposing routes is co-driver work: researching, comparing and recommending are
operational, and none of them commits anything. Nothing here extends what JOE is permitted
to do. See `DISPATCH_DETERMINISTIC_CHASSIS.md` §4 for the operational/authority split.

### Reopening a locked day — CONFIRMED, 30 August 2026

**The operator's ruling: this is volatile and unknowable.** The variety of things that can
happen between a lock and a reopen cannot be enumerated in advance.

**Reopening is not only reactive.** Under the BOOK IT DANO rule, Dispatch continuously
evaluates new opportunities against the locked day and **proposes** reopening when one
materially improves it. A locked plan exists to support profitable operations — it must not
prevent the operator from taking a materially superior load merely because the day was
already approved. See `DISPATCH_CAPACITY_PLAN_DOCTRINE.md` §4.

Both plans are shown side by side. The approved plan stands until a human authorizes the
change; presenting only the proposal would make a recommendation into an act.

**So the design does not try.** When the unknowable is the input, guessing is the failure
mode, not the solution.

```
LOCKED  ──reopen──►  PROPOSED  ──human locks──►  LOCKED
```

1. **Reopening invalidates the lock.** The day returns to `PROPOSED`.
2. **The sequence is re-reasoned from current facts**, not carried forward. The engine knows
   what is true now; it does not know what changed while the day was locked.
3. **The previous locked sequence is preserved as history, never as a default.** It shows
   what was planned and what the human approved — it does not pre-fill the next plan.
4. **A human locks again.** No reopened day proceeds on an engine proposal alone.

Carrying the old sequence forward would be the system asserting that nothing important
changed — a claim it has no basis for. Re-proposing costs the operator one review. Assuming
costs them a wasted day.

### Capacity returned mid-run

**CONFIRMED:** a business may be closed, and that capacity returns the next day or is
rescheduled.

When a stop cannot be served:

1. The stop fails with a reason. It is not silently dropped.
2. That capacity is **freed on today** — the remaining stops may be resequenced.
3. The **allocation is not cancelled.** It moves to another day, keeping its
   `allocation_id`. The commitment to the broker stands; only the day changes.
4. The allocation carries the failed attempt in its history.

**An allocation may therefore span two days.** Freight collected today and delivered
tomorrow is one commitment appearing on two Mission Records — which is why the allocation
identity has to be durable. See §7a.

### Home every day, by business model

**CONFIRMED:** overnight stays are avoided. There is more value in repositioning to
Jacksonville each day than in staying out.

This is not a scoring preference. It is a **constraint on the day**:

```
every day starts and ends at home base
```

Consequences:

- Freight that cannot be delivered and the van returned within the day's hours does not
  fit the day — regardless of how well it scores.
- `reserve_capacity.protect_return_home` is not a tuning knob. It is the business model.
- The existing `return_home_required` and `tomorrow_position_risk` dimensions in
  `dispatch/scoring.py` are more important than they look, because the operation depends
  on them being true.

A multi-day allocation is therefore a **recovery from an exception**, never a plan.

### Planned empty days are legitimate

**CONFIRMED:** empty days will be frequent and seasonal. Florida fruit harvest can mean
daily runs for two or three weeks; empty days are then scheduled deliberately for recovery
and maintenance.

Rules that follow:

1. **A Mission Record may exist with zero allocations.** An empty Tuesday is a record,
   not an absence.
2. **An empty day carries a reason** — `recovery`, `maintenance`, `seasonal`, `personal`.
3. **The system never treats a planned empty day as a problem to solve.** It does not
   surface loads for it, does not warn, and does not ask the operator to justify it.
4. **Capacity on a planned empty day is zero**, so it is blocked to acceptance rather than
   merely unattractive.

Rule 3 matters more than it sounds. A system that nags on a rest day is a system the
operator learns to ignore, and reduced cognitive load is the founding premise.

Seasonality is handled by the profile, not by new code — swapping the profile is how the
operator says *this is harvest season*. See `DISPATCH_POLICY_PROFILE_EXAMPLES.md`.

## 7c. The avoid list is a veto, not a preference

**CONFIRMED, and this corrects the specification.** The operator does not take capacity
from brokers on the avoid list **regardless** — the list exists because of **nonpayment**,
and hauling for a non-payer is working for free.

`DISPATCH_POLICY_PROFILE_SPEC.md` placed brokers under `preferences`, which made this a
soft scoring input. That is wrong. It moves:

```
preferences.brokers.avoid   ──►   a BLOCKING condition
```

A load from an avoided broker is **disqualified**, whatever it pays and however well it
fits. A high rate from someone who does not pay is not a high rate.

**CONFIRMED, 30 August 2026: `BLOCKING` and overridable, not `NOT PERMITTED`.** This is a
business judgement rather than a legal or physical impossibility.

### But the override is not the remedy — the list is

**CONFIRMED: arrears paid moves the broker back to the USE list.**

Brokers therefore hold a **state**, not a score:

| State | Effect |
|---|---|
| **USE** | Normal. Eligible for capacity. |
| **AVOID** | `BLOCKING`. Nonpayment. |

```
AVOID  ──arrears paid──►  USE
```

The correct action when a broker settles up is to **move them to USE** — once, in the
profile, where it is visible and durable. The per-load override exists for the single
awkward case, not as the working method.

This is what `warn_on_repeat_override` in `DISPATCH_OVERRIDE_RULES_SPEC.md` is for: three
overrides against the same broker means the list is stale, and the system should say so
rather than let the operator keep paying the friction.

**Moving a broker between states is a human act, recorded with who and when.** The engine
may observe that payment arrived. It may not move anyone.

## 8. The three open questions — now answerable

The operator's clarification settles what the earlier draft left open.

### Does a multi-stop load complete per stop or at the last stop?

**Both, at different levels.** An **allocation** completes when its own stops are done — broker
X is served at stops 1 and 4 and is finished, whatever remains on the van. The **Mission
Record** completes when every stop is done.

This matters for money: broker X can be invoiced when their freight is delivered, not when
the driver finishes their day.

### Can stops be resequenced after ACCEPT LOAD?

**Yes — resequencing changes the stop sequence, which is a plan, not an allocation, which
is a commitment.** The order of stops was never promised to anyone. What was promised is
each allocation's time window.

The constraint is therefore: **any sequence is permitted that honours every allocation's
window and the vehicle's capacity.** No override is required, because nothing is being
overridden.

### Does dropping a filler stop break the commitment?

**It depends on whether the stop belongs to a Mission or is spare capacity.**

- Dropping a stop that belongs to an **accepted allocation** breaks that commitment to
  that broker. It requires a recorded decision and it affects one broker, not the run.
- Dropping a stop not yet accepted — a `filler` still being considered — costs nothing.
  Nothing was promised.

**`priority` is therefore the operator's classification of a *candidate*, and loses its
force the moment an allocation is accepted.** After acceptance, `filler` and `critical` freight
carry the same commitment; only the operator's willingness to disappoint differs, and that
is a human judgement the system records rather than makes.

## 8b. What this leaves open

**This is the one place the operator's model reaches past Lane B into existing code.**

`dispatch/mission.py` splits a run into two phases:

```python
PICKUP_STATUSES   = {"created", "dispatched", "en_route_pickup", "at_pickup"}
DELIVERY_STATUSES = {"picked_up", "in_transit", "at_delivery", "delivered", ...}
phase_for(status) -> PICKUP | DELIVERY
```

That model assumes **one** pickup and **one** delivery. A milk run with stops
pickup → pickup → delivery → pickup → delivery has no single pickup phase, and the run
crosses back and forth.

**RECOMMENDATION — the minimal change that preserves the doctrine.** Phase becomes a
property of the **current stop**, not of the run:

```
phase = phase_for(current_stop.stop_type)
```

CURRENT still resolves; it never becomes a stored third state. `filter_bundle()` still
reveals rather than deletes. The doctrine in `DISPATCH_STATE_TRANSITION_RULES.md` §6 holds
unchanged — only the input to `phase_for()` changes, from run status to stop type.

With the day's stop sequence in place, `phase_for()` reads the **current stop**. The
three commitment questions this section previously left open are answered in §8 above.

**What genuinely remains open:**

- **Does an allocation rescheduled twice need a limit?** Freight that keeps missing its day
  is a signal, not a routine.
- **What counts as "near" home base** for the close check — a radius, a geofence, or the
  driver's own judgement?
- **HOS:** is 10,000 lb payload or gross vehicle weight rating? Still unanswered, and it
  decides whether FMCSA hours-of-service applies at all.

### Answered by the operator on 30 August 2026

| Question | Ruling |
|---|---|
| Can a commitment span two days? | **Yes** — a business may be closed; capacity returns the next day or is rescheduled. |
| Are overnight stays acceptable? | **No.** More value in repositioning to Jacksonville daily. Multi-day is recovery from an exception, never a plan. |
| Can an avoided broker be carried if convenient? | **No, regardless.** The list exists because of nonpayment; hauling for a non-payer is working for free. |
| Who initiates resequencing? | **The driver.** JOE arranges the exception and presents alternatives; the human decides. |
| Do planned empty days exist? | **Yes, and frequently.** Seasonal — harvest can mean daily runs for weeks, then scheduled days for recovery and maintenance. |
| Who proposes the daily sequence? | **The engine**, reasoning from all available real-time knowledge — at the point the day closes on capacity. The human reviews and locks; the calendar follows. |
| Is the durable `allocation_id` right? | **Yes.** Confirmed. |
| Who may close a day early? | **JOE may propose it; the driver closes it** — usually by powering down at final arrival. JOE is dialog assistant until then. |
| Does a sequence survive a reopen? | **No.** Volatile and unknowable, so the day returns to PROPOSED and is re-reasoned. The old sequence is history, never a default. |
| Is the avoid list overridable? | **Yes, blocking-but-overridable** — but the remedy is the USE list. Arrears paid moves the broker back to USE. |
| Does a power-down always end the day? | **No.** Fuel, breaks and docks all power down. Never close while a commitment is outstanding; ask when ambiguous; stay silent at an ordinary stop. |
| Is 10,000 lb payload or GVWR? | **Payload.** So combined GVWR is materially higher, and the profile defaults to hours-of-service applying. |

## 9. Evaluation fields this adds

New blocking conditions:

| Condition | Source |
|---|---|
| Over weight capacity | already specified |
| **Over cube capacity** | new — needs `cube_capacity_ft3` |
| **Over pallet positions** | new |
| **Incompatible commodities** | new — physical, not a preference |
| Temp control required, not held | new — equipment |
| Hazard flag, endorsement not held | already specified |

New dimensions, joining the six in `DISPATCH_EVALUATION_ENGINE_SPEC.md`:

| Dimension | Question |
|---|---|
| **Utilization** | How full does this leave the van — by weight, cube and pallets? |
| **Service Risk** | Tight windows, high dwell, congestion, appointment vs FCFS |
| **Complexity** | Stops, special handling, compatibility, resequencing constraints |

**Complexity is the dimension none of the prior specifications had**, and it is the one an
owner-operator actually feels. Seven stops with liftgate service and three incompatible
commodities is a hard day. If the engine cannot express that, it will keep recommending
loads that pay well and cost the operator their evening.

Complexity must **never** be folded into the profit score. The whole question — *is the
extra money worth the extra hassle* — only exists while the two are separate.

## 10. The four charts are presentation

Stop Sequence (Gantt), Capacity Utilization, Profitability, and Complexity vs Profit are
**Stage 8** work — see `DISPATCH_AGGRESSIVE_BUILD_SEQUENCE.md`.

They are recorded here because they tell the engine what to produce: every chart needs a
field, and a chart with no field behind it is a chart that will be computed in a template.
That is how the stages merged the first time.

| Chart | Requires |
|---|---|
| Stop Sequence | ordered stops, windows, dwell |
| Capacity Utilization | the three ratios |
| Profitability | revenue per mile **and** per hour, margin |
| Complexity vs Profit | complexity score, profit score — **separate** |

The last row is the argument for §9's final rule in one line: the chart cannot exist if the
two scores are one number.

## 11. Open questions

| # | Question | Blocks |
|---|---|---|
| 12 | **Cube capacity of the van and trailer?** | All cube utilization. Two of three ratios work without it; the third is guesswork. |
| 13 | **Your accessorial rates** — detention per hour, layover, TONU, lumper, liftgate. | Every profitability figure. Linehaul-only evaluation is wrong for this work. |
| 14 | **Target margin**, for the profit score. | Profit scoring has no reference point. |
| 15 | **Complexity tolerance** — how many stops before a load stops being worth it? | Complexity scoring bands. |
| 16 | **Can stops be resequenced or dropped after acceptance?** | The commitment model in §8. |
