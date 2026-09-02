"""ARRIVE: the one act that puts mail in front of a broker by itself.

Pressing ARRIVE creates a documented arrival event -- date, time, GPS,
facility, load number -- and produces the Arrival Notice from it.

    Its purpose is on-time arrival evidence, independent of warehouse gate
    processes.

That independence is the whole point. The truck's record of when it arrived
does not depend on a gate guard logging anything, which is why the notice is
worth nothing if it is not contemporaneous, and why this is the only outbound
act in the system that does not wait for a human.

VETTING PERIOD
==============

The first four notices are **drafted, not sent.** The operator reads them in
Outlook and confirms the template says what he wants said under his company's
name. After the fourth there is no reason to keep drafting: the notice is one
fixed template filled from the load card and the arrival event, with no
per-broker variation to re-check.

The count is derived from the records rather than stored in a counter. A
counter is a second source of truth that can disagree with what actually
happened; counting the notices that exist cannot.
"""

from __future__ import annotations

from datetime import datetime, timezone

#: How many notices are drafted for review before the template is trusted.
VETTING_NOTICES = 4

#: Every arrival notice is blind-copied here. The office holds the evidence
#: whether or not the driver is reachable later.
NOTICE_BCC = "Ops@l1truck.com"


def notices_produced(records) -> int:
    """How many arrival notices this build has already drafted or sent."""
    produced = 0
    for record in _iter(records):
        if record.get("arrival_notice_sent_at") or \
                record.get("arrival_notice_drafted_at"):
            produced += 1
    return produced


def vetting_remaining(records) -> int:
    """Notices still to be drafted before the template is trusted."""
    return max(0, VETTING_NOTICES - notices_produced(records))


def should_draft(records) -> bool:
    """Whether this notice is drafted for review rather than sent.

    True for the first four. After that the template has been read four times
    under real load numbers, and drafting a fixed template a fifth time only
    adds a step between arrival and the evidence of it.
    """
    return vetting_remaining(records) > 0


def _iter(records):
    if records is None:
        return []
    if hasattr(records, "values"):
        return [r for r in records.values() if isinstance(r, dict)]
    return [r for r in records if isinstance(r, dict)]


def notice_text(notice: dict) -> str:
    """The Arrival Notice as the broker reads it.

    One template. Filled from the load card and the arrival event, with no
    per-broker variation -- which is what makes four readings enough to trust
    it. Empty fields are left empty: a notice that invents a facility name is
    worse than one admitting it does not have it, and this goes out under
    Level 1 Transport's name.
    """
    lines = [notice.get("title", "ARRIVAL NOTICE"), "",
             notice.get("opening", "Truck arrived on site."), ""]
    for field in notice.get("fields") or []:
        value = str(field.get("value") or "").strip()
        if value:
            lines.append("%s: %s" % (field.get("key"), value))
    lines += ["", notice.get("follows_intro", ""), ""]
    for item in notice.get("follows") or []:
        lines.append("  - %s" % item)
    # The reply path, last. A notice that reports an arrival and gives the
    # reader no way to answer it is a broadcast rather than a communication.
    lines += ["", "Level 1 Transport",
              "Jacksonville Regional Micro-Response Carrier",
              NOTICE_BCC]
    return "\n".join(lines)


def deliver(record: dict, notice: dict, *, records=None, mail=None,
            recipient: str = "") -> dict:
    """Draft or send the notice, and say which happened.

    Returns what the record should carry. It never claims a send it did not
    make: a driver who believes the broker already has his arrival evidence
    does not chase it.
    """
    now = datetime.now(timezone.utc).isoformat()
    recipient = str(recipient or "").strip()
    drafting = should_draft(records)

    if mail is None:
        return {"ok": False, "sent": False, "drafted": False,
                "arrival_notice_error": "no mail connector",
                "note": "Dispatch has your arrival on record with the time."}

    if not recipient:
        return {"ok": False, "sent": False, "drafted": False,
                "arrival_notice_error": "no recipient on the record",
                "note": ("Dispatch has your arrival on record. There is no "
                         "contact address for this one, so nothing went out.")}

    subject = "Arrival Notice - %s - %s" % (
        (record.get("numbers") or {}).get("load_label")
        or record.get("load_number") or "",
        notice.get("phase", ""))
    body = notice_text(notice)

    operation = mail.draft if drafting else mail.send
    result = operation(recipient, subject, body, bcc=NOTICE_BCC)

    if not result.get("ok"):
        return {"ok": False, "sent": False, "drafted": False,
                "arrival_notice_error": result.get("blocker", ""),
                "note": "Dispatch has your arrival on record with the time."}

    if drafting:
        return {"ok": True, "sent": False, "drafted": True,
                "arrival_notice_drafted_at": now,
                "vetting_remaining": max(0, vetting_remaining(records) - 1),
                "note": ("Arrival notice is in your Drafts. Read it, then send "
                         "it. %d more to check before it goes on its own."
                         % max(0, vetting_remaining(records) - 1))}

    return {"ok": True, "sent": True, "drafted": False,
            "arrival_notice_sent_at": now,
            "note": "Arrival notice sent."}
