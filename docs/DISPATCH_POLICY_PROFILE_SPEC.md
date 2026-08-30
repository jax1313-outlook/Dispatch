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
    "home_base": "Jacksonville, FL",
    "trucks": 1
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
    "fuel_cost_per_mile": 0.62,
    "minimum_revenue": 0,
    "deadhead": { "acceptable_miles": 150, "maximum_miles": 300,
                  "charge_against_rate": true }
  },

  "capability": {
    "equipment": ["dry_van"],
    "endorsements": [],
    "weight_limit_lbs": 45000,
    "operating_radius_miles": 500,
    "hours_available_default": 11.0,
    "drive_speed_mph": 50
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
    "brokers":   { "preferred": [], "avoid": [] },
    "customers": { "preferred": [], "avoid": [] }
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
| `_OPERATING_RADIUS_MILES` | `capability.operating_radius_miles` |
| `_FUEL_COST_PER_MILE` | `money.fuel_cost_per_mile` |
| `_RATE_PER_MILE_FLOOR / _GOOD / _EXCELLENT` | `money.rate_per_mile.*` |
| `_WEIGHT_LIMIT_LBS` | `capability.weight_limit_lbs` |
| `_HOURS_AVAILABLE_DEFAULT` | `capability.hours_available_default` |
| `_DRIVE_SPEED_MPH` | `capability.drive_speed_mph` |

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
