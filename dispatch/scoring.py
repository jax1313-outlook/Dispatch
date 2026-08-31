"""Dispatch load scoring engine — deterministic rule module.

Computes operational risk assessments and an overall load score from
structured load data.  All logic is deterministic: same inputs always
produce the same outputs.  No LLM calls, no network requests.

Outputs:
    - 6 Position/HOS fields (position_impact, return_home_required,
      tomorrow_position_risk, hos_risk, route_risk, economic_opportunity_flag)
    - 2 route economics (deadhead_miles, fuel_estimate)
    - 1 overall score (0-100)

The module uses configurable home base and operating parameters so it
works for any single-truck owner-operator without external dependencies.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta

_HOME_BASE = "Jacksonville, FL"

_OPERATING_RADIUS_MILES = 500

_FUEL_COST_PER_MILE = 0.62

_HOURS_AVAILABLE_DEFAULT = 11.0
_DRIVE_SPEED_MPH = 50

_RATE_PER_MILE_FLOOR = 2.50
_RATE_PER_MILE_GOOD = 4.00
_RATE_PER_MILE_EXCELLENT = 5.50

_WEIGHT_LIMIT_LBS = 45000

#: The highest score `compute_score` can produce, and the figure the
#: classification bands are calibrated against.
#:
#: It is 90 rather than 100 because broker confidence held ten points and was
#: removed -- trust is not a program variable. The ceiling is named here because
#: it was previously implicit in a clamp, which is how removing a dimension could
#: silently rescale every band without anything failing.
MAX_SCORE = 90

_KNOWN_DISTANCES: dict[tuple[str, str], float] = {
    ("jacksonville", "savannah"): 140,
    ("jacksonville", "atlanta"): 345,
    ("jacksonville", "orlando"): 140,
    ("jacksonville", "tampa"): 200,
    ("jacksonville", "miami"): 345,
    ("jacksonville", "charlotte"): 395,
    ("jacksonville", "tallahassee"): 165,
    ("jacksonville", "columbia"): 305,
    ("jacksonville", "birmingham"): 475,
    ("jacksonville", "charleston"): 245,
    ("savannah", "atlanta"): 250,
    ("savannah", "charlotte"): 260,
    ("savannah", "charleston"): 110,
    ("atlanta", "charlotte"): 245,
    ("atlanta", "birmingham"): 150,
    ("atlanta", "orlando"): 440,
    ("atlanta", "tampa"): 460,
    ("orlando", "tampa"): 85,
    ("orlando", "miami"): 235,
    ("tampa", "miami"): 280,
    ("charlotte", "columbia"): 90,
    ("tallahassee", "atlanta"): 270,
}


def _normalize_city(location: str) -> str:
    if not location:
        return ""
    city = location.split(",")[0].strip().lower()
    city = re.sub(r"\s+", " ", city)
    return city


def _lookup_distance(origin: str, destination: str) -> float | None:
    a = _normalize_city(origin)
    b = _normalize_city(destination)
    if not a or not b:
        return None
    if a == b:
        return 0.0
    return _KNOWN_DISTANCES.get((a, b)) or _KNOWN_DISTANCES.get((b, a))


def _estimate_deadhead(destination: str) -> float | None:
    return _lookup_distance(destination, _HOME_BASE)


def _parse_window_start(window: str | None) -> datetime | None:
    if not window:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", window)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return None


def _parse_window_end(window: str | None) -> datetime | None:
    if not window:
        return None
    parts = window.split(" - ")
    if len(parts) != 2:
        return None
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", window)
    if not date_match:
        return None
    date_str = date_match.group(1)
    time_match = re.match(r"(\d{2}:\d{2})", parts[1].strip())
    if not time_match:
        return None
    try:
        return datetime.strptime(f"{date_str} {time_match.group(1)}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def compute_position_impact(load: dict) -> str:
    destination = load.get("destination", "")
    distance_home = _lookup_distance(destination, _HOME_BASE)
    if distance_home is None:
        return "Unknown"
    if distance_home <= 50:
        return "Favorable — delivers near home base"
    if distance_home <= 150:
        return "Acceptable — short deadhead home"
    if distance_home <= 300:
        return "Moderate — extended deadhead required"
    return "Unfavorable — significant repositioning needed"


def compute_return_home(load: dict) -> str:
    destination = load.get("destination", "")
    distance_home = _lookup_distance(destination, _HOME_BASE)
    delivery_end = _parse_window_end(load.get("delivery_window"))

    if distance_home is None:
        return "Unknown"

    drive_hours = distance_home / _DRIVE_SPEED_MPH

    if distance_home <= 50:
        return "Same-day return likely"

    if delivery_end:
        hour = delivery_end.hour
        if hour <= 14 and drive_hours <= 6:
            return f"Same-day return possible ({drive_hours:.1f}h drive)"
        if drive_hours <= _HOURS_AVAILABLE_DEFAULT:
            return f"Next-day return ({drive_hours:.1f}h drive)"
        return f"Multi-day return ({drive_hours:.1f}h drive, layover required)"

    if drive_hours <= _HOURS_AVAILABLE_DEFAULT:
        return f"Return requires {drive_hours:.1f}h drive"
    return f"Extended return — {drive_hours:.1f}h drive, layover required"


def compute_tomorrow_position_risk(load: dict) -> str:
    destination = load.get("destination", "")
    dest_city = _normalize_city(destination)
    home_city = _normalize_city(_HOME_BASE)

    if not dest_city:
        return "Unknown"

    distance_home = _lookup_distance(destination, _HOME_BASE)
    if distance_home is None:
        return "Unknown — destination not in route database"

    if dest_city == home_city or distance_home <= 50:
        return "Low — at or near home base"

    has_outbound = False
    for (a, b) in _KNOWN_DISTANCES:
        if a == dest_city or b == dest_city:
            other = b if a == dest_city else a
            if other != home_city:
                has_outbound = True
                break

    if has_outbound:
        if distance_home <= 200:
            return "Low — near home with relay options"
        return "Medium — relay options available from destination"
    return "High — limited outbound options from destination"


def compute_hos_risk(load: dict) -> str:
    """Drive-time risk ESTIMATED from distance and the appointment window.

    This is not an hours-of-service reading and must never be presented as one.
    Dispatch is not an ELD, holds no duty-clock data, and has no telematics feed
    of any kind -- the driver is responsible for legal HOS compliance
    (Operational Readiness Mission Section 1.6). What this computes is how much
    of a normal driving day a lane consumes at a nominal speed, which is a
    planning signal and nothing more.

    The key and the function keep their historical `hos_` names so no caller or
    stored record changes shape; every surface that DISPLAYS the value labels it
    as an estimate.
    """
    distance = load.get("distance_miles")
    if distance is None:
        return "Unknown"

    drive_time = distance / _DRIVE_SPEED_MPH
    pickup_start = _parse_window_start(load.get("pickup_window"))
    delivery_end = _parse_window_end(load.get("delivery_window"))

    if drive_time <= 5:
        base = "Low"
    elif drive_time <= 8:
        base = "Medium"
    elif drive_time <= _HOURS_AVAILABLE_DEFAULT:
        base = "High"
    else:
        return (
            f"Critical — {drive_time:.1f}h estimated drive time exceeds a single "
            f"driving day. Estimated from distance; Dispatch holds no ELD reading."
        )

    if pickup_start and delivery_end:
        available = (delivery_end - pickup_start).total_seconds() / 3600
        if available < drive_time + 1:
            return f"High — tight window ({available:.1f}h for {drive_time:.1f}h drive)"

    return f"{base} — {drive_time:.1f}h estimated drive time (no ELD reading)"


def compute_route_risk(load: dict) -> str:
    risks = []

    weight = load.get("weight_lbs")
    if weight and weight > _WEIGHT_LIMIT_LBS:
        risks.append(f"overweight ({weight:,} lbs)")

    equip_match = load.get("equipment_match", "")
    if equip_match == "mismatch":
        risks.append("equipment mismatch")

    distance = load.get("distance_miles")
    if distance and distance > _OPERATING_RADIUS_MILES:
        risks.append(f"outside operating radius ({distance} mi)")

    if load.get("hard_stop"):
        reason = load.get("hard_stop_reason", "unspecified")
        risks.append(f"hard stop: {reason}")

    detention = load.get("detention_history", "")
    if detention and "high" in detention.lower():
        risks.append("high detention history")

    # "unknown broker" is deliberately not a risk. Trust is assumed until broken
    # and is not a program variable, so an unfamiliar broker is an unfamiliar
    # broker -- not a hazard the engine has detected.

    if not risks:
        return "Low — no risk factors identified"
    if len(risks) == 1:
        return f"Medium — {risks[0]}"
    return f"High — {'; '.join(risks)}"


def compute_economic_opportunity(load: dict) -> str:
    rate = load.get("rate")
    distance = load.get("distance_miles")

    if rate is None or distance is None or distance == 0:
        return "Unknown — rate or distance data missing"

    rpm = rate / distance
    fuel_cost = distance * _FUEL_COST_PER_MILE
    net = rate - fuel_cost
    margin_pct = (net / rate) * 100 if rate > 0 else 0

    deadhead = _estimate_deadhead(load.get("destination", ""))
    if deadhead:
        total_miles = distance + deadhead
        effective_rpm = rate / total_miles
        deadhead_note = f", effective RPM with deadhead: ${effective_rpm:.2f}"
    else:
        deadhead_note = ""

    if rpm >= _RATE_PER_MILE_EXCELLENT:
        flag = "Strong"
    elif rpm >= _RATE_PER_MILE_GOOD:
        flag = "Good"
    elif rpm >= _RATE_PER_MILE_FLOOR:
        flag = "Acceptable"
    else:
        flag = "Below floor"

    return f"{flag} — ${rpm:.2f}/mi, ${net:.0f} net after fuel ({margin_pct:.0f}% margin{deadhead_note})"


def compute_deadhead_miles(load: dict) -> float | None:
    return _estimate_deadhead(load.get("destination", ""))


def compute_fuel_estimate(load: dict) -> float | None:
    distance = load.get("distance_miles")
    if distance is None:
        return None
    deadhead = compute_deadhead_miles(load) or 0
    return round((distance + deadhead) * _FUEL_COST_PER_MILE, 2)


def compute_score(load: dict) -> int:
    """Compute an overall load score (0-100) from load data.

    Scoring dimensions (deterministic weights):
        Rate quality:       30 points
        Route efficiency:   20 points
        Equipment match:    15 points
        Position value:     15 points
        Operational risk:   10 points

    The maximum is therefore **90, not 100**. Broker confidence held the missing
    ten and was removed rather than redistributed: reassigning them would mean
    deciding that rate quality is now worth 33 instead of 30, which is a business
    judgement and belongs to the operator, not to this change.

    Band thresholds were set against a 100-point maximum and have not been
    revisited. They are policy values and are reviewed when the weights move into
    the Policy Profile.
    """
    score = 0.0

    rate = load.get("rate")
    distance = load.get("distance_miles")
    if rate and distance and distance > 0:
        rpm = rate / distance
        if rpm >= _RATE_PER_MILE_EXCELLENT:
            score += 30
        elif rpm >= _RATE_PER_MILE_GOOD:
            score += 30 * ((rpm - _RATE_PER_MILE_FLOOR) / (_RATE_PER_MILE_EXCELLENT - _RATE_PER_MILE_FLOOR))
            score = min(score, 30)
        elif rpm >= _RATE_PER_MILE_FLOOR:
            score += 15 * ((rpm - _RATE_PER_MILE_FLOOR) / (_RATE_PER_MILE_GOOD - _RATE_PER_MILE_FLOOR))
        # below floor: 0 points
    elif rate is None:
        score += 5  # unknown rate gets small benefit of the doubt

    if distance:
        if distance <= _OPERATING_RADIUS_MILES:
            route_score = 20 * (1 - (distance / (_OPERATING_RADIUS_MILES * 1.5)))
            score += max(route_score, 5)
        else:
            over = distance - _OPERATING_RADIUS_MILES
            penalty = min(over / 500, 1.0) * 15
            score += max(5 - penalty, 0)

    equip_match = load.get("equipment_match", "")
    if equip_match == "match":
        score += 15
    elif equip_match == "mismatch":
        score += 0
    else:
        score += 7

    dest = load.get("destination", "")
    dist_home = _lookup_distance(dest, _HOME_BASE)
    if dist_home is not None:
        if dist_home <= 50:
            score += 15
        elif dist_home <= 150:
            score += 12
        elif dist_home <= 300:
            score += 7
        else:
            score += 3
    else:
        score += 5

    weight = load.get("weight_lbs")
    op_risk = 10.0
    if weight and weight > _WEIGHT_LIMIT_LBS:
        op_risk -= 4
    if load.get("hard_stop"):
        op_risk -= 5
    detention = load.get("detention_history", "")
    if detention and "high" in detention.lower():
        op_risk -= 3
    score += max(op_risk, 0)

    # Broker trust is deliberately absent. It was worth 10 points of 100 here --
    # 10 for a broker the string-match believed reliable, 3 for one it did not
    # recognise -- which is the engine forming a judgement the operator has ruled
    # is his, and penalising an unknown broker 7 points when trust is assumed
    # until broken. See docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md section 3:
    # trust is not a program variable. It is not scored, inferred or stored.

    return max(0, min(MAX_SCORE, round(score)))


def score_load(load: dict) -> dict:
    """Run all scoring computations on a load and return the full result.

    Returns a dict with all 6 Position/HOS fields, route economics,
    and the overall score.
    """
    return {
        "position_impact": compute_position_impact(load),
        "return_home_required": compute_return_home(load),
        "tomorrow_position_risk": compute_tomorrow_position_risk(load),
        "hos_risk": compute_hos_risk(load),
        "route_risk": compute_route_risk(load),
        "economic_opportunity_flag": compute_economic_opportunity(load),
        "deadhead_miles": compute_deadhead_miles(load),
        "fuel_estimate": compute_fuel_estimate(load),
        "score": compute_score(load),
    }
