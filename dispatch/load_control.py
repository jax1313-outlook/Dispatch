"""Load control: who to call when something is wrong with the freight.

**Load control is not the broker.** It is whoever holds authority over the
freight on a given stop, and on a real run that is not one party:

    "Had a load that had one broker, 2 stops, different companies. One stop had
     the shipper as the load control, not the broker. That meant if issues or
     damage, call the shipper -- not the broker."

So load control is a fact about **the stop**, not about the run. A truck can
carry freight arranged by one broker where authority on stop 1 sits with that
broker and authority on stop 2 sits with the shipper; it can equally carry
three brokers' freight to three companies in one run.

Getting this wrong is not a display problem. It is reporting damage to a party
who is not responsible for the freight, while the party who is has not been
told -- on a clock, from a dock, with a receiver waiting.

This is why the Mission Record stays one record. The broker was never a
mission-level identity. **Load control is stop-level, and always was.**
"""

from __future__ import annotations

#: Which party holds authority for a stop. Recorded, never assumed -- the whole
#: point is that it differs between stops on the same run.
BROKER = "BROKER"
SHIPPER = "SHIPPER"
CUSTOMER = "CUSTOMER"
CONSIGNEE = "CONSIGNEE"
ROLES = (BROKER, SHIPPER, CUSTOMER, CONSIGNEE)

#: What the driver sees on the stop card. Short, because it sits next to a
#: phone number he is about to dial.
ROLE_LABELS = {
    BROKER: "Broker",
    SHIPPER: "Shipper",
    CUSTOMER: "Customer",
    CONSIGNEE: "Consignee",
}

_ALIASES = {
    "broker": BROKER, "brokerage": BROKER, "3pl": BROKER,
    "shipper": SHIPPER, "supplier": SHIPPER, "vendor": SHIPPER,
    "customer": CUSTOMER, "client": CUSTOMER, "account": CUSTOMER,
    "consignee": CONSIGNEE, "receiver": CONSIGNEE,
}


def normalise_role(raw: str) -> str:
    """Read a role the way it gets written down. Unknown stays unknown.

    An unrecognised role is left empty rather than guessed at BROKER: the
    default that looks harmless is exactly the wrong call on the stop where
    the shipper holds control.
    """
    return _ALIASES.get(str(raw or "").strip().lower(), "")


def label_for(role: str) -> str:
    return ROLE_LABELS.get(normalise_role(role), "")


def control_for(stop: dict, mission_default: dict | None = None) -> dict:
    """Who to call about the freight on this stop.

    Falls back to the run's default only when the stop names nobody -- a single
    broker over every stop is still the common case, and repeating him on each
    line is how a template stops getting filled in.

    `known` is False when nobody has been named anywhere. The screen says so
    rather than showing the facility's dock contact and letting the driver
    assume it is the same thing.
    """
    stop = stop or {}
    default = mission_default or {}

    name = str(stop.get("control_name") or "").strip()
    role = normalise_role(stop.get("control_role"))
    phone = str(stop.get("control_phone") or "").strip()
    reference = str(stop.get("control_ref") or "").strip()
    inherited = False

    if not name:
        name = str(default.get("control_name") or "").strip()
        role = role or normalise_role(default.get("control_role"))
        phone = phone or str(default.get("control_phone") or "").strip()
        inherited = bool(name)

    return {
        "known": bool(name),
        "name": name,
        "role": role,
        "role_label": label_for(role),
        "phone": phone,
        "reference": reference,
        "inherited": inherited,
        # What the driver reads on the stop card, in one line.
        "line": _line(name, label_for(role), phone),
    }


def _line(name: str, role_label: str, phone: str) -> str:
    if not name:
        return "Load control not recorded"
    parts = name
    if role_label:
        parts += f" ({role_label})"
    if phone:
        parts += f" · {phone}"
    return parts


def differs_across(stops: list, mission_default: dict | None = None) -> bool:
    """Whether this run carries more than one point of authority.

    When it does, the stop card has to name the party -- which is a deliberate
    reversal of the rule that broker identity lives in one place only. That
    rule was written for a run with one broker, and it holds for one; it fails
    the run where stop 2 answers to somebody else.
    """
    seen = set()
    for stop in stops or []:
        control = control_for(stop, mission_default)
        if control["known"]:
            seen.add((control["name"].lower(), control["role"]))
    return len(seen) > 1
