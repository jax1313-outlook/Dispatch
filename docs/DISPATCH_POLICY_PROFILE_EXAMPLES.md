# DISPATCH POLICY PROFILE EXAMPLES

Status: SPECIFICATION — worked examples. Not implemented. Values are illustrative and
require Mike's confirmation before any become defaults.

---

## 1. Why examples

A specification states what is possible. An example states what it looks like when a real
operator uses it. These four profiles describe the same truck under four different
business situations — and nothing but the profile changes between them.

That is the test of the whole design: **if changing the business requires changing code,
the design has failed.**

---

## 2. Profile A — Level 1 Transport, today

Single truck, Jacksonville, Southeast footprint, revenue focus, home most weekends.

```json
{
  "profile_version": "1.0.0",
  "profile_name": "L1 - single truck, southeast, revenue",
  "identity": { "home_base": "Jacksonville, FL", "trucks": 1 },

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
    "fuel_cost_per_mile": 0.62,
    "deadhead": { "acceptable_miles": 150, "maximum_miles": 300 }
  },

  "capability": {
    "equipment": ["dry_van"], "endorsements": [],
    "weight_limit_lbs": 45000, "operating_radius_miles": 500,
    "hours_available_default": 11.0, "drive_speed_mph": 50
  },

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

Same truck. Thursday. The only thing that matters is being home Friday night.

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

Truck payment due. Nothing matters but money in this week.

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

## 6. What changed across all four

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

## 7. What no profile can do

None of the four can:

- accept a load
- send anything
- skip the human
- override a `NOT PERMITTED` condition
- fabricate a missing value

There is no key for any of it. The profile controls **evaluation**. Authority is not
configurable — see `DISPATCH_POLICY_PROFILE_SPEC.md` §4.6.

---

## 8. Confirmation needed

Every number above is either recovered from July 2026 or lifted from current code. None
has been confirmed as still correct.

| Value | Source | Still right? |
|---|---|---|
| Territory tiers | v1.3.3, 13 Jul 2026 | ? |
| Rate floor $2.50 | `dispatch/scoring.py` | ? |
| Fuel $0.62/mi | `dispatch/scoring.py` | ? |
| Weight limit 45,000 lbs | `dispatch/scoring.py` | ? |
| Radius 500 mi | `dispatch/scoring.py` | ? |
| Sweep times 06:00/12:00/18:00 | v1.1, v1.3.3 | ? |
| Equipment: dry van only | INFERRED — never stated anywhere | ? |

The last row is the weakest. No build in the lineage records what the truck actually
is. Everything about equipment matching is currently guesswork.
