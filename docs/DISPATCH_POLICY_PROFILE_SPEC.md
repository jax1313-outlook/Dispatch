# DISPATCH POLICY PROFILE SPEC

Status: SPECIFICATION. Not implemented. No runtime behaviour is changed by this document.

---

## 1. What the profile is

The Policy Profile is the single file that holds every business judgement Dispatch makes.
It is the operator's file. Editing it changes how the engine evaluates, and requires no
programmer.

**The engine is in the code. The business is in the profile.** If a value describes Level 1
Transport rather than describing arithmetic, it belongs here.

## 2. Location and format

```
config/policy_profile.json          the operator's live profile
config/policy_profile.default.json  shipped defaults, never edited in place
```

JSON, because it already is elsewhere in the lineage and Mike can read and edit it in any
text editor. A settings screen comes later and edits this same file.

## 3. Structure

```json
{
  "profile_version": "1.0.0",
  "profile_name": "Level 1 Transport - single truck",
  "effective_from": "2026-09-01",

  "identity": {
    "home_base": "Jacksonville, FL"
  },

  "territory": {
    "tiers": {
      "core":       { "states": ["FL","GA","SC","AL","MS","TN"], "points": 15,
                      "status": "CORE SERVICE AREA",
                      "reason": "Inside core operating footprint." },
      "acceptable": { "states": ["NC","LA","KY","VA"], "points": 5,
                      "status": "ACCEPTABLE SERVICE AREA",
                      "reason": "Within acceptable operating range." },
      "expansion":  { "states": ["TX","AR","WV","MD","DC","OH","IN"], "points": -5,
                      "status": "EXPANSION REVIEW",
                      "reason": "Outside core footprint; may be viable with expansion capital." },
      "hard_no":    { "states": ["AK","HI","CA","OR","WA"], "points": -40,
                      "status": "HARD-NO LOCATION",
                      "reason": "Outside practical operating footprint.",
                      "severity": "BLOCKING" }
    },
    "unknown": { "points": -5, "status": "UNKNOWN LOCATION",
                 "reason": "Location could not be confidently classified." }
  },

  "money": {
    "rate_per_mile": { "floor": 2.50, "good": 4.00, "excellent": 5.50 },
    "minimum_revenue": 0,
    "deadhead": { "acceptable_miles": 150, "maximum_miles": 300,
                  "charge_against_rate": true }
  },

  "fleet": [
    {
      "id": "van-1",
      "name": "Cargo van + trailer",
      "active": true,
      "acquired": "2026-08-30",
      "retired": null,
      "equipment": ["cargo_van", "trailer"],
      "endorsements": [],
      "trailer_length_ft": null,
      "pallet_positions": 6,
      "weight_limit_lbs": 10000,
      "cube_capacity_ft3": null,
      "temp_control": false,
      "liftgate": false,
      "operating_radius_miles": 500,
      "hours_available_default": 11.0,
      "drive_speed_mph": 50,
      "fuel_cost_per_mile": 0.62
    }
  ],

  "accessorials": {
    "detention_per_hour": null,
    "detention_free_minutes": 120,
    "layover": null,
    "tonu": null,
    "lumper": null,
    "liftgate": null,
    "temp_control": null
  },

  "utilization": {
    "target_weight": 0.85,
    "target_cube": 0.85,
    "target_pallet": 0.85,
    "underutilised_below": 0.50
  },

  "complexity": {
    "stops_comfortable": 3,
    "stops_maximum": null,
    "dwell_minutes_concern": 60,
    "penalise_non_stackable": true
  },

  "reserve_capacity": {
    "protect_return_home": true,
    "minimum_hours_reserved": 0,
    "no_new_commitment_within_hours_of_home": 0
  },

  "growth": {
    "objective": "revenue",
    "expansion_review_minimum_score": 45
  },

  "preferences": {
    "brokers":   { "preferred": [] },
    "customers": { "preferred": [], "avoid": [] }
  },

  "_comment_avoid": "Broker avoid is NOT a preference - see blocking_conditions.",
  "broker_avoid_list": {
    "brokers": [],
    "severity": "BLOCKING",
    "reason": "Nonpayment. Hauling for a non-payer is working for free."
  },

  "blocking_conditions": [],
  "filter_rules": {},
  "score_weights": {},
  "sort_rules": {},
  "recommendation_rules": {},
  "confidence_rules": {},
  "override_rules": {},

  "schedule": {
    "sweep_times": ["06:00", "12:00", "18:00"],
    "timezone": "America/New_York"
  }
}
```

The seven `_rules` / `_weights` / `blocking_conditions` blocks are specified in their own
documents. They live in this one file.

## 4. Rules

### 4.1 Nothing business-specific in code

If a value describes Level 1 Transport — a state, a rate, a truck, a preference, a
threshold — it is in the profile. The engine holds only mechanics.

### 4.2 Defaults ship and are honest

A fresh install works. Any value still at its default is **marked as a default** in the
interface, so the operator can tell what they have set from what they have inherited.

### 4.3 Validation is total, and failure is loud

On load, the profile is validated whole. If it fails:

- Dispatch reports which key failed and why, in plain language
- Dispatch runs on the **last known-good profile**, and says so
- Dispatch **never partially applies** a profile

A half-applied profile is the worst possible state: the operator believes one set of rules
is in force while another is running.

### 4.4 Versioned, and stamped onto evaluations

`profile_version` is recorded with every evaluation. Without it, a score cannot be
explained six weeks later, and a past decision cannot be audited.

Changing the profile does **not** rescore existing records. See
`DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md` §5.

### 4.5 One profile, one operator

No per-screen overrides, no hidden defaults elsewhere in the code. One file is in force at
a time.

### 4.6 The profile cannot grant authority

**Binding.** No key in this file may enable Dispatch to decide, approve, send, book or
accept. The profile tunes evaluation. It does not touch the authority model.

There is deliberately no `auto_accept`, no `auto_decline`, no `auto_send`. Adding one
would make human final authority a setting, and a setting can be changed by accident.

### 4.7 UNKNOWN is configured, not defaulted

Every dimension states explicitly what an unknown value scores. Nothing silently
becomes `0` or `no risk`.

### 4.8 The fleet is a list, and it changes

**Required by the operator, 30 August 2026: equipment must be alterable as the operation
expands and changes.**

The fleet is an array, not a set of fixed keys. A single van today, a van and a box truck
next year, a different trailer next month — all of it is editing the profile, and none of
it is a code change.

1. **Adding a vehicle is adding an object.** Nothing else in Dispatch changes.
2. **Retiring is `"active": false`, never deletion.** A retired vehicle stays in the
   profile so past evaluations still explain themselves. Delete it and every load it ever
   carried becomes unexplainable.
3. **Capacity is per vehicle.** Pallets, weight, radius, hours, drive speed and fuel cost
   all belong to the vehicle, because a van and a box truck differ in every one of them.
   Fuel in particular is a property of the vehicle, not of the business.
4. **Capability is evaluated against the active fleet.** A load is blocked on capability
   only when **no active vehicle can take it**. With one van that reads identically to
   today; with three it is the only correct rule.
5. **The evaluation records which vehicle it matched** (`matched_vehicle`). Without it, a
   fleet of two makes every score ambiguous — the operator cannot tell which vehicle the
   engine was reasoning about.
6. **No vehicle, no fabrication.** An empty or fully-retired fleet does not fall back to a
   default truck. Capability dimensions return `UNKNOWN` and confidence drops, exactly as
   any other missing fact would.

Rule 2 is the one that will feel wrong and is not. Retiring rather than deleting is what
keeps a decision made in 2026 explicable in 2028.

## 5. Lineage

**CONFIRMED.** This is a recovery, not an invention.

| Element | From |
|---|---|
| Externalised weights in a config file | v1.0.1 `config/scoring_rules.json` |
| Keyword and NAICS watchlists in config | v1.0.1, v1.3.3 |
| Four-tier territory with status and reason | v1.3.3 `settings.json` |
| Explicit unknown-location handling | v1.3.3 `score_location()` |
| Sweep times in config | v1.1 / v1.3.3 (`"times": ["06:00","12:00","18:00"]`) |
| Severity on hard_no | **new** — v1.3.3 had the tier but not the veto |

## 6. Migration from current code

These constants move out of `dispatch/scoring.py` into the profile. No behaviour change is
intended by the move itself — same values, new home.

| Constant | Profile key |
|---|---|
| `_HOME_BASE` | `identity.home_base` |
| `_RATE_PER_MILE_FLOOR / _GOOD / _EXCELLENT` | `money.rate_per_mile.*` |
| `_OPERATING_RADIUS_MILES` | `fleet[].operating_radius_miles` |
| `_FUEL_COST_PER_MILE` | `fleet[].fuel_cost_per_mile` |
| `_WEIGHT_LIMIT_LBS` | `fleet[].weight_limit_lbs` |
| `_HOURS_AVAILABLE_DEFAULT` | `fleet[].hours_available_default` |
| `_DRIVE_SPEED_MPH` | `fleet[].drive_speed_mph` |
| *(none — new)* | `fleet[].pallet_positions` |

The bottom five belong to a **vehicle**, not to the business, so they move into `fleet`
rather than into a flat `capability` block. `fuel_cost_per_mile` in particular is a
property of what you are driving.

**Two of these values change as they move, and that is a behaviour change, not a
migration.** `_WEIGHT_LIMIT_LBS` goes from 45,000 to 10,000, and `_FUEL_COST_PER_MILE`
needs the operator's real figure. Land the move first with values byte-identical to today,
then correct them in a separate, visible commit — so if scores shift, it is obvious which
change did it.

`_KNOWN_DISTANCES` stays in code. It is reference data, not policy — it describes
geography, not Level 1 Transport.

## 7. Open questions for Mike

1. **Territory tiers** — the states above are v1.3.3's from July. Still right?
2. **Rate floor** — is $2.50/mile still the floor, and is $5.50 still excellent?
3. **Fuel** — $0.62/mile is from the current code. What is it actually costing now?
4. **Reserve Capacity** — the keys are stubs. What is the real rule? "Never commit to a
   load that puts me more than N hours from home on a Friday" is the kind of thing that
   belongs here, and only you can state it.
5. **Growth objective** — `revenue` or `expansion`? v1.3.3 modelled both.
