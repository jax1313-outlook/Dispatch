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

**CONFIRMED by arithmetic:** all three land on the same 10,000 lb ceiling. These are not
three capacity rules — they are **one weight limit expressed at three pallet weights**,
capped at 6 positions by deck space.

So the vehicle carries two hard limits and one unknown:

```
weight_limit_lbs   10000    CONFIRMED
pallet_positions       6    CONFIRMED
cube_capacity_ft3      ?    UNKNOWN - needed
```

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

## 7a. Two levels: the Run and the Mission

**CONFIRMED by the operator, 30 August 2026:** the van's capacity may be filled by one
broker for the whole vehicle, or shared across several brokers going to several stops.
This is the LTL and courier model, and it is the normal case, not an edge case.

That single fact requires a level Dispatch does not have.

### The conflict it exposes

The Mission Record carries **dual numbering** — our mission number and *the broker's* load
number, preserved exactly. With three brokers on one van, there is no single broker load
number. Either the record stops being one broker's commitment, or something above it
holds the vehicle.

### The resolution — two records, two different jobs

```
Run  (the plan for the vehicle)          Tuesday, van-1, stops 1..7
 ├── Mission A   broker X, load 847261    pallets 2, stops 1 and 4
 ├── Mission B   broker Y, load 55120     pallets 3, stops 2 and 6
 └── Mission C   broker Z, load A-9931    pallets 1, stops 3 and 7
```

| | **Mission** | **Run** |
|---|---|---|
| What it is | A **commitment to a broker** | A **plan for the vehicle** |
| Identity | Mission number + their load number | Run id + date + vehicle |
| Created by | ACCEPT LOAD | Assigning a Mission to a day |
| Changeable | No — a promise was made | **Yes — freely, until executed** |
| Owns | The freight, the rate, the customer | The stop order, the vehicle, the day |
| Completes | When *its* stops are done | When *all* its stops are done |

**Everything already specified about the Mission Record stands unchanged.** Dual numbering,
one record one identity, progressive enrichment, ACCEPT LOAD as the irreversible gate — all
of it holds. The Run does not replace the Mission; it **schedules** it.

### Capacity binds at the Run, not the Mission

This is the consequence that changes evaluation most.

```
run.weight_utilization = Σ(mission weights on this run) ÷ vehicle.weight_limit_lbs
run.pallet_utilization = Σ(mission pallets on this run) ÷ vehicle.pallet_positions
run.cube_utilization   = Σ(mission cube    on this run) ÷ vehicle.cube_capacity_ft3
```

A Mission of two pallets is never "over capacity" by itself. It is over capacity **on a
particular run**, and only when added to what is already there.

**So the real evaluation question is not "does this load fit the van?" — it is "does this
load still fit Tuesday?"** Capacity is contextual. An opportunity must be evaluated against
**remaining** capacity on a candidate run, and the same opportunity can be a comfortable
fit on Wednesday and blocked on Tuesday.

`DISPATCH_EVALUATION_ENGINE_SPEC.md` gains a `candidate_run` input for this reason. With no
run in view it falls back to the empty vehicle, which is the single-broker FTL case — the
model degrades correctly to the simple shape.

### Stop numbering and the calendar

Both belong to the Run, and both are now explained:

- **Stop #** is a position in the Run's sequence — not a property of any one Mission. This
  is why the portal showed it: with three brokers aboard, stop order is the only thing that
  describes the driver's actual day.
- **The calendar shows Runs**, and within a day, its stops in order. A Mission appears on
  the calendar *through* the Run that carries it.

## 8. The three open questions — now answerable

The operator's clarification settles what the earlier draft left open.

### Does a multi-stop load complete per stop or at the last stop?

**Both, at different levels.** A **Mission** completes when its own stops are done — broker
X is served at stops 1 and 4 and is finished, whatever remains on the van. The **Run**
completes when every stop is done.

This matters for money: broker X can be invoiced when their freight is delivered, not when
the driver finishes their day.

### Can stops be resequenced after ACCEPT LOAD?

**Yes — resequencing changes the Run, which is a plan, not the Mission, which is a
commitment.** The order of stops was never promised to anyone. What was promised is each
Mission's time window.

The constraint is therefore: **any sequence is permitted that honours every Mission's
window and the vehicle's capacity.** No override is required, because nothing is being
overridden.

### Does dropping a filler stop break the commitment?

**It depends on whether the stop belongs to a Mission or is spare capacity.**

- Dropping a stop that belongs to an **accepted Mission** breaks that Mission's commitment
  to that broker. It requires a recorded decision and it affects one broker, not the run.
- Dropping a stop not yet accepted — a `filler` still being considered — costs nothing.
  Nothing was promised.

**`priority` is therefore the operator's classification of a *candidate*, and loses its
force the moment a Mission is accepted.** After acceptance, `filler` and `critical` freight
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

With the Run in place, `phase_for()` reads the **current stop of the current Run**. The
three commitment questions this section previously left open are answered in §8 above.

**What genuinely remains open**, and belongs to the operator rather than to this document:

- **Can a Mission span two Runs?** Freight picked up Tuesday and delivered Thursday sits on
  the van overnight. The model permits it; whether the operation does is a business
  question.
- **Can a Run carry Missions for a broker on the avoid list**, if another broker's freight
  is already aboard and the stop is on the way?
- **Who resequences — the operator, or the engine proposing an order for approval?** The
  engine may recommend a sequence. It may not commit one.
- **Does a Run need its own record before any Mission is accepted?** A planned empty
  Tuesday is either a real object or nothing at all.

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
