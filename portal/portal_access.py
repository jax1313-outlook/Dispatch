"""Customer Portal access -- the Mission Visibility Key -- issued when a load is committed.

Doctrine: DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md, Section 4A. The
Customer Load Number acts as a Mission Visibility Key; it is not a username,
account, company login or organizational credential.

Mike Zachary, 2026-09-13: "Customer Load Number from Load card will be the
Customer PIN and auto sent to the email on file at the time of the load
commital as a separate email template explaining the use of the Portal and
it's entry system. This is part of the On-boarding Packet."

So at COMMIT (portal/routes/joe_portal.py::mission_commit):

  1. the load number on the load card becomes a Mission Visibility Key for the customer
     on the card, in the Library PIN Service, named for the Operations person
     who pressed COMMIT; and
  2. its own email -- templates/onboarding/customer_portal_access.txt, one of
     the ONBOARDING_PACKET templates -- goes to the customer's email on file.

The outcome is recorded on the mission record as it happened, including what
did not happen and why. Nothing is sent when the PIN could not be made: an
email announcing a load number that does not open the portal is worse than no
email. A load number already held by another customer is never re-pointed, so
no email is sent for it either -- one customer never gets into another's view.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import render_template

from portal import brief
from portal.models import pin_service

#: The Onboarding Packet's email templates, under templates/onboarding/.
ONBOARDING_PACKET = ("customer_portal_access",)

TEMPLATE = "onboarding/customer_portal_access.txt"
PORTAL_URL_ENV = "DISPATCH_PORTAL_URL"
COMMIT_CHANNEL = "LOAD_COMMIT"


def customer_email(record: dict) -> str:
    """The customer's email on file: the record's customer email, else the broker's."""
    return (brief._record_value(record, "customer_email")
            or str((record.get("card_data") or {}).get("broker_email") or "").strip())


def load_number(record: dict) -> str:
    return brief._record_value(record, "load_number")


def portal_url(fallback_root: str) -> str:
    base = os.environ.get(PORTAL_URL_ENV, "").strip() or fallback_root
    return base.rstrip("/") + "/portal/login"


def issue(record: dict, *, committed_by: str | None, mail_connector, url_root: str) -> dict:
    """Make the Mission Visibility Key and send the portal access email. Returns what happened.

    `mail_connector` is called only when there is an email to send.
    """
    outcome = {"template": "customer_portal_access", "at": datetime.now(timezone.utc).isoformat(),
               "pin": "NOT_CREATED", "sent": False, "to": []}

    def stop(note):
        outcome["note"] = note
        return outcome

    customer = brief._record_value(record, "customer")
    number = load_number(record)
    email = customer_email(record)
    person = (committed_by or "").strip()

    if not pin_service.configured():
        return stop("The Library PIN Service is not configured on this server, so no Mission Visibility Key was made "
                    "and no portal email was sent.")
    if not person:
        return stop("Nobody was signed in to Operations by name at COMMIT, so no Mission Visibility Key was made "
                    "and no portal email was sent.")
    if not customer:
        return stop("The load card names no customer, so no Mission Visibility Key was made.")
    if not number:
        return stop("The load card has no load number, so no Mission Visibility Key was made.")

    try:
        added = pin_service.add_customer_load(customer, number, requested_by=person, channel=COMMIT_CHANNEL)
    except pin_service.PinRefused as exc:
        return stop(f"No Mission Visibility Key was made and no portal email was sent: {exc}.")
    except pin_service.PinServiceUnavailable as exc:
        return stop(f"No Mission Visibility Key was made and no portal email was sent: {exc}")
    outcome["pin"] = "ALREADY_PRESENT" if added.get("already_present") else "CREATED"

    if not email:
        return stop(f"The load number now opens {customer}'s portal, but there is no customer email on file, "
                    "so the portal email was not sent.")
    mail = mail_connector()
    if mail is None:
        return stop("The load number now opens the portal, but there is no mail connector on this machine, "
                    "so the portal email was not sent.")

    subject = f"Your Level 1 Transport Customer Portal - Load {number}"
    body = render_template(TEMPLATE, customer=customer, load_number=number, portal_url=portal_url(url_root))
    try:
        result = mail.send([email], subject, body)
    except Exception as exc:  # noqa: BLE001 - a mail failure is reported, never raised through COMMIT
        result = {"ok": False, "blocker": str(exc)}
    outcome["to"] = [email]
    if not result.get("ok"):
        return stop(f"The load number now opens the portal, but the email to {email} did not go out: "
                    f"{result.get('blocker') or 'the mail connector said no'}.")
    outcome["sent"] = True
    return stop(f"Portal access sent to {email}.")
