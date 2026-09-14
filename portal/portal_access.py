"""Customer Portal access -- the Mission Visibility Key -- issued when a load is committed.

Doctrine: DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md, Section 4A. The
Customer Load Number acts as a Mission Visibility Key; it is not a username,
account, company login or organizational credential.

Mike Zachary, 2026-09-13: "Customer Load Number from Load card will be the
Customer PIN and auto sent to the email on file at the time of the load
commital as a separate email template explaining the use of the Portal and
it's entry system. This is part of the On-boarding Packet."

At COMMIT (portal/routes/joe_portal.py::mission_commit) the email travels the
Mission Visibility Communication Flow (playbook Section 4A; Mike Zachary,
2026-09-13: "route the access email through Joe, Publisher, COMI and Email
Helper"). Joe owns Mission Visibility communication; the Mission Record
remains the source of truth.

  Mission Record Updates           COMMIT.
  Joe Updates Mission Visibility   the load number on the load card becomes the
                                   Mission Visibility Key for the customer on the
                                   card (Library PIN Service), named for the
                                   Operations person who pressed COMMIT.
  Joe Evaluates Communication      the customer must be told, when there is an
    Requirements                   email on file.
  Publisher Creates                templates/onboarding/customer_portal_access.txt
                                   (ONBOARDING_PACKET), on a Publisher card.
  COMI Routes                      trigger mission_visibility_opened -> customer
                                   email.
  Email Helper Sends               through the mail connector, or dispatch.mail.

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


def joe_update_mission_visibility(record: dict, *, committed_by: str | None) -> dict:
    """Joe Updates Mission Visibility: the load number becomes this mission's Mission Visibility Key."""
    customer = brief._record_value(record, "customer")
    number = load_number(record)
    person = (committed_by or "").strip()

    def closed(note):
        return {"opened": False, "pin": "NOT_CREATED", "note": note}

    if not pin_service.configured():
        return closed("The Library PIN Service is not configured on this server, so no Mission Visibility Key "
                      "was made and no portal email was sent.")
    if not person:
        return closed("Nobody was signed in to Operations by name at COMMIT, so no Mission Visibility Key was "
                      "made and no portal email was sent.")
    if not customer:
        return closed("The load card names no customer, so no Mission Visibility Key was made.")
    if not number:
        return closed("The load card has no load number, so no Mission Visibility Key was made.")
    try:
        added = pin_service.add_customer_load(customer, number, requested_by=person, channel=COMMIT_CHANNEL)
    except pin_service.PinRefused as exc:
        return closed(f"No Mission Visibility Key was made and no portal email was sent: {exc}.")
    except pin_service.PinServiceUnavailable as exc:
        return closed(f"No Mission Visibility Key was made and no portal email was sent: {exc}")
    return {"opened": True, "pin": "ALREADY_PRESENT" if added.get("already_present") else "CREATED",
            "customer": customer, "load_number": number, "requested_for": person}


def joe_evaluate_communication(record: dict, visibility: dict) -> dict:
    """Joe Evaluates Communication Requirements: tell the customer how to open their window."""
    if not visibility.get("opened"):
        return {"required": False, "note": visibility["note"]}
    email = customer_email(record)
    if not email:
        return {"required": False,
                "note": f"The load number now opens {visibility['customer']}'s Mission Visibility View, but there "
                        "is no customer email on file, so the portal email was not sent."}
    return {"required": True, "template": "customer_portal_access", "recipient_role": "customer", "to": email}


def issue(record: dict, *, committed_by: str | None, mail_connector, url_root: str) -> dict:
    """Run the Mission Visibility Communication Flow for a committed load. Returns what happened.

    `mail_connector` is called only when there is an email to send.
    """
    from dispatch import comi_routing
    from portal.models import email_helper, publisher

    outcome = {"template": "customer_portal_access", "at": datetime.now(timezone.utc).isoformat(),
               "pin": "NOT_CREATED", "sent": False, "to": [], "flow": {}}

    def stop(note):
        outcome["note"] = note
        return outcome

    # Joe
    visibility = joe_update_mission_visibility(record, committed_by=committed_by)
    outcome["pin"] = visibility["pin"]
    outcome["flow"]["joe"] = {"mission_visibility": "OPENED" if visibility.get("opened") else "NOT_OPENED"}
    requirement = joe_evaluate_communication(record, visibility)
    outcome["flow"]["joe"]["communication_required"] = requirement["required"]
    if not requirement["required"]:
        return stop(requirement["note"])

    # Publisher
    number = visibility["load_number"]
    action = publisher.create_customer_communication(
        record.get("id") or "", template=requirement["template"], to=requirement["to"],
        subject=f"Your Level 1 Transport Customer Portal - Load {number}",
        body=render_template(TEMPLATE, customer=visibility["customer"], load_number=number,
                             portal_url=portal_url(url_root)),
        trigger_reason="COMMIT opened Mission Visibility for the customer", requested_for=visibility["requested_for"])
    outcome["flow"]["publisher"] = {"action_id": action["id"], "status": action["status"]}

    # COMI
    evaluation = comi_routing.evaluate_comi_routing(record.get("id") or "", comi_routing.MISSION_VISIBILITY_OPENED,
                                                    source_refs={"publisher_action_id": action["id"]})
    route = comi_routing.route_communication(evaluation, action)
    outcome["flow"]["comi"] = {"communication_event_id": evaluation["communication_event_id"],
                               "channel": route.get("channel"), "status": route["status"]}
    outcome["to"] = route.get("to") or [requirement["to"]]

    # Email Helper
    sent = email_helper.send_communication(route, sent_by=visibility["requested_for"], mail_connector=mail_connector)
    outcome["flow"]["email_helper"] = {"transport": sent["transport"], "sent": sent["sent"]}
    action = publisher.record_communication_result(action["id"], sent)
    outcome["flow"]["publisher"]["status"] = action["status"]
    if not sent["sent"]:
        return stop(f"The load number now opens the Mission Visibility View, but the email to "
                    f"{', '.join(outcome['to'])} did not go out: {sent['detail']}.")
    outcome["sent"] = True
    return stop(f"Portal access sent to {', '.join(outcome['to'])}.")
