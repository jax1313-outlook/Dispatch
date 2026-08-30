# DISPATCH POLICY PROFILE EXAMPLES

Status: SPECIFICATION — worked examples. Not implemented. Values are illustrative and
require Mike's confirmation before any become defaults.

---

## 1. Why examples

A specification states what is possible. An example states what it looks like when a real
operator uses it. Profiles A to D describe the same vehicle under four different
business situations; Profile E changes the vehicle — and nothing but the profile changes between them.

That is the test of the whole design: **if changing the business requires changing code,
the design has failed.**

---

## 2. Profile A — Level 1 Transport, today

Cargo van with trailer. Jacksonville, Southeast footprint, revenue focus, home most
weekends.

```json
{
  "profile_version": "1.0.0",
  "profile_name": "L1 - single truck, southeast, revenue",
  "identity": { "home_base": "Jacksonville, FL" },

  "territory": {
    "tiers": {
      "core":       { "states": ["FL","GA","SC","AL","MS","TN"], "points": 15,
                      "status": "CORE SERVICE AREA" },
      "acceptable": { "states": ["NC","LA","KY","VA"], "points": 5,
                      "status": "ACCEPTABLE SERVICE AREA" },
      "expansion":  { "states": ["TX","AR","WV","MD","DC","OH","IN"], "points": -5,
                      "status": "EXPANSION REVIEW" },
      "hard_no":    { "states": ["CA","OR","WA","NV","AZ","ID","MT","WY","AK","HI"],
                      "points": -40, "status": "HARD-NO LOCATION",
                      "severity": "BLOCKING" }
    },
    "unknown": { "points": -5, "status": "UNKNOWN LOCATION" }
  },

  "money": {
    "rate_per_mile": { "floor": 2.50, "good": 4.00, "excellent": 5.50 },
    "deadhead": { "acceptable_miles": 150, "maximum_miles": 300 }
  },

  "fleet": [
    { "id": "van-1", "name": "Cargo van + trailer", "active": true,
      "equipment": ["cargo_van","trailer"], "endorsements": [],
      "pallet_capacity": 6, "weight_limit_lbs": 10000,
      "operating_radius_miles": 500,
      "hours_available_default": 11.0, "drive_speed_mph": 50,
      "fuel_cost_per_mile": 0.62 }
  ],

  "reserve_capacity": { "protect_return_home": true },
  "growth": { "objective": "revenue" },

  "score_weights": {
    "operational_fit": 25, "financial_value": 30,
    "return_position_value": 20, "growth_potential": 15, "territory": 10
  },

  "schedule": { "sweep_times": ["06:00","12:00","18:00"],
                "timezone": "America/New_York" }
}
```

Every value here is recovered from either v1.3.3's config or current
`dispatch/scoring.py`. Nothing is invented.

---

## 3. Profile B — home for the weekend

Same vehicle. Thursday. The only thing that matters is being home Friday night.

**Changed from A:**

```json
"reserve_capacity": {
  "protect_return_home": true,
  "no_new_commitment_within_hours_of_home": 14,
  "minimum_hours_reserved": 11
},
"score_weights": {
  "operational_fit": 20, "financial_value": 15,
  "return_position_value": 50, "growth_potential": 0, "territory": 15
},
"filter_rules": { "maximum_deadhead_miles": 150 }
```

Return position value goes from 20 to 50 and financial value drops from 30 to 15. A
$5.00/mile load to Texas now scores below a $3.00/mile load to Savannah, because this week
that is the correct answer.

**Nothing in the engine knows what a weekend is.** The operator moved five numbers.

---

## 4. Profile C — expansion

Debt cleared, looking to open a new lane rather than maximise this month.

**Changed from A:**

```json
"territory": {
  "tiers": {
    "expansion": { "states": ["TX","AR","WV","MD","DC","OH","IN"],
                   "points": 10, "status": "EXPANSION REVIEW" }
  }
},
"growth": { "objective": "expansion", "expansion_review_minimum_score": 35 },
"score_weights": {
  "operational_fit": 20, "financial_value": 20,
  "return_position_value": 10, "growth_potential": 40, "territory": 10
},
"money": { "rate_per_mile": { "floor": 2.20, "good": 3.50, "excellent": 5.00 } }
```

Expansion territory flips from a `-5` penalty to a `+10` bonus. Growth potential becomes
the heaviest dimension. The rate floor drops, because a lane worth opening is worth
opening at a thinner margin.

This is the profile v1.3.3 was reaching for with its `growth()` function and never got to
express, because its weights were in code.

---

## 5. Profile D — tight cash

Vehicle payment due. Nothing matters but money in this week.

**Changed from A:**

```json
"money": { "rate_per_mile": { "floor": 3.00, "good": 4.00, "excellent": 5.50 },
           "minimum_revenue": 1200 },
"filter_rules": { "minimum_revenue": 1200, "maximum_deadhead_miles": 100 },
"score_weights": {
  "operational_fit": 15, "financial_value": 60,
  "return_position_value": 15, "growth_potential": 0, "territory": 10
},
"growth": { "objective": "revenue" }
```

Note that `minimum_revenue` appears **twice**, deliberately, and does two different things:

- in `filter_rules` it **excludes** loads under $1,200 from the lane entirely
- in `money` it informs **scoring** for those that remain

That is the filter/score separation doing visible work. The operator can also set the
filter and leave the score alone — see the short list, but score honestly.

---

## 6. Profile E — the fleet grows

Same operator, a year on. The van is still running; a box truck has been added, and the
original trailer has been retired.

**Changed from A** — only the `fleet` array:

```json
"fleet": [
  { "id": "van-1", "name": "Cargo van + trailer", "active": true,
    "equipment": ["cargo_van","trailer"], "endorsements": [],
    "pallet_capacity": 6, "weight_limit_lbs": 10000,
    "operating_radius_miles": 500, "fuel_cost_per_mile": 0.62 },

  { "id": "box-1", "name": "26ft box truck", "active": true,
    "acquired": "2027-04-12",
    "equipment": ["box_truck","liftgate"], "endorsements": [],
    "pallet_capacity": 12, "weight_limit_lbs": 26000,
    "operating_radius_miles": 700, "fuel_cost_per_mile": 0.48 },

  { "id": "trailer-old", "name": "Original trailer", "active": false,
    "retired": "2027-03-01",
    "equipment": ["trailer"], "pallet_capacity": 4,
    "weight_limit_lbs": 7000, "fuel_cost_per_mile": 0.62 }
]
```

What this changes in behaviour, with **no code touched**:

- A 10-pallet load was **blocked** under Profile A. Under E it is admitted and matched to
  `box-1`. The blocking condition did not change — the fleet did.
- A load needing a liftgate was previously blocked on equipment. Now it matches.
- Fuel is computed per vehicle, so the same load shows a different margin depending on
  which vehicle takes it.
- `trailer-old` is retired, not deleted. Every load it carried in 2026 still explains
  itself, and it can never be matched to new work.

This is the requirement stated on 30 August 2026 — *"I need the ability to alter equipment
as I expand and change"* — working as a data edit.

## 7. What changed across profiles A to D

| | A | B | C | D |
|---|---|---|---|---|
| Financial value weight | 30 | 15 | 20 | **60** |
| Return position weight | 20 | **50** | 10 | 15 |
| Growth weight | 15 | 0 | **40** | 0 |
| Rate floor | 2.50 | 2.50 | **2.20** | **3.00** |
| Expansion territory | −5 | −5 | **+10** | −5 |
| Max deadhead | 300 | **150** | 300 | **100** |

**Lines of Python changed: zero.**

That is the doctrine working. The engine did not learn about weekends, debt or expansion.
It applied the same arithmetic to different numbers, and the operator moved the numbers.

---

## 8. What no profile can do

None of the four can:

- accept a load
- send anything
- skip the human
- override a `NOT PERMITTED` condition
- fabricate a missing value

There is no key for any of it. The profile controls **evaluation**. Authority is not
configurable — see `DISPATCH_POLICY_PROFILE_SPEC.md` §4.6.

---

## 9. Confirmation needed

Every number above is either recovered from July 2026 or lifted from current code. None
has been confirmed as still correct.

| Value | Source | Still right? |
|---|---|---|
| **Vehicle: cargo van + trailer** | **operator, 30 Aug 2026** | **CONFIRMED** |
| **Pallet capacity: 6** | **operator, 30 Aug 2026** | **CONFIRMED** |
| **Weight limit: 10,000 lb** | **operator, 30 Aug 2026** | **CONFIRMED** |
| Territory tiers | v1.3.3, 13 Jul 2026 | ? |
| Radius 500 mi | `dispatch/scoring.py` | ? |
| Sweep times 06:00/12:00/18:00 | v1.1, v1.3.3 | ? |
| Rate floor $2.50 / good $4.00 / excellent $5.50 | `dispatch/scoring.py` | **likely wrong** |
| Fuel $0.62/mi | `dispatch/scoring.py` | **likely wrong** |
| HOS 11 hours | `dispatch/scoring.py` | **needs a ruling** |

The last three rows are now the weak ones, and they are weak for the same reason: they
were calibrated for a Class 8 tractor-trailer.

- **Rate bands** are truckload figures. This is expedite and courier work — a different
  market with different rates. The right numbers are the ones the operator actually books
  at, and only he has them.
- **Fuel at $0.62/mi** implies roughly 6 mpg. A cargo van does substantially better, so
  every net-revenue figure Dispatch shows today is pessimistic.
- **HOS at 11 hours** assumes FMCSA hours-of-service applies. Whether it does depends on
  the combined gross vehicle weight rating of van plus trailer, and on whether the
  10,000 lb figure is payload or GVWR. **This is a regulatory question, not an
  architectural one — it needs the operator's answer, not an assumption from this
  document.**
