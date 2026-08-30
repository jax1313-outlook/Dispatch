# DISPATCH CONFIGURABLE BUSINESS POLICY DOCTRINE

Status: DOCTRINE. No runtime behaviour is changed by this document.

---

## 1. The division

**Dispatch owns the engine. The operator owns the settings.**

The engine knows *how* to evaluate. It does not know *what Level 1 Transport considers a
good load*. That belongs to the person who owns the truck, and it changes — with the
season, the fuel price, the debt position, and the driver's own plans.

A business rule welded into code is a rule the operator must ask a programmer to change.
That is a failure of the product, not a limitation of the operator.

## 2. What must be configurable

Nothing on this list may be a code constant.

**Territory**
- Operating territories and their tiers
- Location categories, location status values, and the reason text for each
- Home base

**Money**
- Revenue thresholds; rate-per-mile floor / good / excellent
- Deadhead thresholds and how deadhead is charged against a load
- Fuel cost per mile

**Capability**
- Equipment and endorsements held
- Weight limits
- Hours-of-service assumptions and the drive-speed planning figure

**Judgement**
- Risk tolerances
- Reserve Capacity rules
- Growth objectives
- Broker preferences and customer preferences
- Recommendation rules — which bands map to which action
- Confidence rules
- Override rules — who may override what, and what must be recorded

## 3. Precedent: this was already solved, and then lost

**CONFIRMED.** v1.0.1 externalised its scoring into `config/scoring_rules.json` on
13 July 2026:

```json
{
  "weights": {
    "naics_fit": 25, "sdvosb_or_vosb": 25, "small_business": 10,
    "scope_keywords": 20, "southeast_location": 10,
    "deadline_feasible": 10, "risk_penalty": -20
  },
  "priority_keywords": ["ltl", "freight", "trucking", "..."],
  "southeast_states": ["FL","GA","SC","NC","TN","AL","MS","KY"]
}
```

The weights, the vocabulary and the footprint were all editable without touching Python.
This survived v1.1, v1.3 and v1.3.1.

v1.3.3 and GOLD both dropped `scoring_rules.json`. v1.3.3 moved territory into
`settings.json` — a better model, see §4 — but hard-coded the points. GOLD hard-coded
everything it kept.

**Current Dispatch is less configurable than July.** `dispatch/scoring.py` holds these as
module constants:

```python
_HOME_BASE = "Jacksonville, FL"
_OPERATING_RADIUS_MILES = 500
_FUEL_COST_PER_MILE = 0.62
_RATE_PER_MILE_FLOOR = 2.50
_RATE_PER_MILE_GOOD = 4.00
_RATE_PER_MILE_EXCELLENT = 5.50
_WEIGHT_LIMIT_LBS = 45000
_HOURS_AVAILABLE_DEFAULT = 11.0
```

Every one of those is a business policy, not an engine mechanic. Fuel at $0.62 per mile is
a fact with a shelf life measured in weeks.

## 4. The best territory model in the lineage

**CONFIRMED.** v1.3.3 `config/settings.json` — four tiers, fully externalised, with
distinct handling for the unknown case:

```json
"location_rules": {
  "core":       ["FL","GA","SC","AL","MS","TN"],
  "acceptable": ["NC","LA","KY","VA"],
  "expansion":  ["TX","AR","WV","MD","DC","OH","IN"],
  "hard_no":    ["AK","HI","CA", "...30 states"]
}
```

This is the model Dispatch should adopt. Note what v1.3.3 got right and what it got wrong:

- **Right:** tiers, not a binary in/out. Reason text carried with the status. An explicit
  `UNKNOWN LOCATION` state scored separately from a known-bad one.
- **Wrong:** `HARD-NO LOCATION` scored `-40` points instead of blocking. Its own reason
  text says *"manual override only"* — but nothing in the code enforces that. A strong
  opportunity in California still classified as `POSSIBLE MATCH`.

Dispatch takes the tiers **and** restores the veto. See `DISPATCH_OVERRIDE_RULES_SPEC.md`.

## 5. Rules for the profile itself

1. **Defaults ship, and they are honest.** A fresh install works, and shows which values
   are defaults rather than the operator's own.
2. **Editable without a programmer.** A structured file now, a settings screen later.
3. **Validated on load.** A malformed profile fails loudly. It never partially applies.
4. **Versioned.** The profile in force when a record was evaluated is recorded with that
   record, or the score cannot be explained afterwards.
5. **One profile, one operator.** No hidden per-screen overrides.
6. **The profile cannot grant authority.** No setting may enable the system to decide,
   approve or send.

Rule 6 is the boundary between this doctrine and the authority model. It is not
negotiable by configuration — a setting that could grant authority would make the
authority model advisory.
