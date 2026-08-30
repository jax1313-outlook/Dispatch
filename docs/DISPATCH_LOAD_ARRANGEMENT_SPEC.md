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

## 8. Impact on the Mission Record — needs a ruling

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

**What this does not settle**, and should not be settled by this document:

- Does a multi-stop load complete when the last stop completes, or per stop?
- Can a stop be skipped or resequenced after ACCEPT LOAD, and does that need an override?
- Is a `filler` stop droppable without breaking the commitment to the broker?

Those are commitment questions, not data-model questions. They belong to the operator.

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
