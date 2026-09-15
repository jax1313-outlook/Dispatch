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


#: The Customer Portal is FROZEN. Mike Zachary, 2026-09-14: the Stakeholder portal is
#: parked for now ("Stake holder can be parked for now"), then, between freezing and
#: parking it, "freeze it". Frozen means the customer messages still go out -- the
#: portal-access email at COMMIT and the Customer Alerts for securement and freight
#: condition photos -- but no longer point the customer at a portal they cannot reach
#: from outside the truck. The Mission Visibility Key is still made at COMMIT, and the
#: portal code is untouched.
#:
#: Unfreezing is an Owner ruling, not a setting: DISPATCH_PORTAL_URL also carries the
#: address in Dispatch's own approval links, so setting it must not quietly reopen this.
CUSTOMER_PORTAL_FROZEN = True


def customer_portal_link(fallback_root: str) -> str:
    """The portal address for a customer message, or "" while the portal is frozen."""
    return "" if CUSTOMER_PORTAL_FROZEN else portal_url(fallback_root)


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


def customer_contact(record: dict) -> tuple[str | None, str]:
    """Where the customer is told: the email on the load card, else the customer phone number.

    Mike Zachary, 2026-09-14: "the customer email address will be provided information on the
    load card when created. if no address then use customer Phone Number."
    """
    email = customer_email(record)
    if email:
        return "email", email
    phone = brief._record_value(record, "customer_phone")
    return ("text", phone) if phone else (None, "")


def joe_evaluate_communication(record: dict, visibility: dict) -> dict:
    """Joe Evaluates Communication Requirements: tell the customer how to open their window."""
    if not visibility.get("opened"):
        return {"required": False, "note": visibility["note"]}
    channel, to = customer_contact(record)
    if not channel:
        return {"required": False,
                "note": f"The load number now opens {visibility['customer']}'s Mission Visibility View, but there "
                        "is no customer email or phone number on file, so the portal access message was not sent."}
    return {"required": True, "template": "customer_portal_access", "recipient_role": "customer", "to": to,
            "channel": channel}


def _publish_route_send(outcome: dict, record: dict, *, trigger: str, template: str, to: str, subject: str,
                        body: str, trigger_reason: str, requested_for: str, action_type: str, auto_send_basis: str,
                        mail_connector, channel: str = "email") -> dict:
    """Publisher Creates -> COMI Routes -> Email Helper Sends. Fills outcome["flow"] and outcome["to"]."""
    from dispatch import comi_routing
    from portal.models import email_helper, publisher

    # Publisher
    action = publisher.create_customer_communication(
        record.get("id") or "", template=template, to=to, subject=subject, body=body,
        trigger_reason=trigger_reason, requested_for=requested_for, action_type=action_type,
        auto_send_basis=auto_send_basis, channel=channel)
    outcome["flow"]["publisher"] = {"action_id": action["id"], "status": action["status"]}

    # COMI
    evaluation = comi_routing.evaluate_comi_routing(record.get("id") or "", trigger,
                                                    source_refs={"publisher_action_id": action["id"]},
                                                    custom_notes={"recipient_channel": channel})
    route = comi_routing.route_communication(evaluation, action)
    outcome["flow"]["comi"] = {"communication_event_id": evaluation["communication_event_id"],
                               "channel": route.get("channel"), "status": route["status"]}
    outcome["to"] = route.get("to") or [to]

    # Email Helper
    sent = email_helper.send_communication(route, sent_by=requested_for, mail_connector=mail_connector)
    outcome["flow"]["email_helper"] = {"transport": sent["transport"], "sent": sent["sent"]}
    action = publisher.record_communication_result(action["id"], sent)
    outcome["flow"]["publisher"]["status"] = action["status"]
    outcome["sent"] = bool(sent["sent"])
    return sent


def issue(record: dict, *, committed_by: str | None, mail_connector, url_root: str) -> dict:
    """Run the Mission Visibility Communication Flow for a committed load. Returns what happened.

    `mail_connector` is called only when there is an email to send.
    """
    from dispatch import comi_routing
    from portal.models import publisher

    outcome = {"template": "customer_portal_access", "at": datetime.now(timezone.utc).isoformat(),
               "pin": "NOT_CREATED", "sent": False, "to": [], "flow": {}}

    def stop(note):
        outcome["note"] = note
        return outcome

    # Joe
    visibility = joe_update_mission_visibility(record, committed_by=committed_by)
    outcome["pin"] = visibility["pin"]
    outcome["flow"]["joe"] = {"mission_visibility": "OPENED" if visibility.get("opened") else "NOT_OPENED"}
    if visibility.get("opened"):
        # Who opened the window: later Customer Alerts for this mission are sent for this person.
        outcome["requested_for"] = visibility["requested_for"]
    requirement = joe_evaluate_communication(record, visibility)
    outcome["flow"]["joe"]["communication_required"] = requirement["required"]
    if not requirement["required"]:
        return stop(requirement["note"])

    number = visibility["load_number"]
    channel = requirement["channel"]
    link = customer_portal_link(url_root)
    if channel == "text" and link:
        body = (f"Level 1 Transport: follow your mission, load {number}, in our Customer Portal: "
                f"{link} - sign in with your load number.")
    elif channel == "text":
        body = (f"Level 1 Transport: thank you for load {number}. We will send you updates as your "
                f"mission moves.")
    else:
        body = render_template(TEMPLATE, customer=visibility["customer"], load_number=number, portal_url=link)
    subject = (f"Your Level 1 Transport Customer Portal - Load {number}" if link
               else f"Level 1 Transport - Load {number}: Mission Visibility")
    sent = _publish_route_send(
        outcome, record, trigger=comi_routing.MISSION_VISIBILITY_OPENED, template=requirement["template"],
        to=requirement["to"], subject=subject, body=body,
        trigger_reason="COMMIT opened Mission Visibility for the customer", requested_for=visibility["requested_for"],
        action_type=publisher.CUSTOMER_PORTAL_ACCESS_ACTION_TYPE, auto_send_basis=publisher.PORTAL_ACCESS_AUTO_SEND,
        mail_connector=mail_connector, channel=channel)
    kind = "text message" if channel == "text" else "email"
    if not sent["sent"]:
        return stop(f"The load number now opens the Mission Visibility View, but the portal access {kind} to "
                    f"{', '.join(outcome['to'])} did not go out: {sent['detail']}.")
    return stop(f"Portal access sent to {', '.join(outcome['to'])}.")


# ── Customer Alerts: mission evidence ─────────────────────────────────────────
#
# Mike Zachary, 2026-09-13: "Load securement photos are a customer-facing Mission Visibility
# artifact." They "become part of: Mission Visibility, Customer Alerts, Mission Record history,
# Final mission package." Customer Portal = pull visibility; Customer Alerts = push visibility.

EVIDENCE_ALERT_TEMPLATE = "mission_visibility/evidence_alert.txt"


def mission_record_for_load(load_id: str) -> tuple[str, dict] | tuple[None, None]:
    """The committed Mission Record Dispatch opened as this load."""
    from dispatch import commitment
    from portal.models import sandbox

    for record_id, record in sandbox.get_all().items():
        if load_id in (record.get("engine_load_id"), record.get("id") or record_id) and commitment.is_committed(record):
            return record_id, record
    return None, None


def alert_mission_evidence(load_id: str, photos: list[dict], *, mail_connector, url_root: str) -> dict:
    """New securement / freight condition photos: Mission Record history, then a Customer Alert
    through Joe -> Publisher -> COMI -> Email Helper. Returns what happened; never raises."""
    from dispatch import comi_routing
    from portal.models import publisher, sandbox

    now = datetime.now(timezone.utc).isoformat()
    outcome = {"template": "evidence_alert", "at": now, "sent": False, "to": [], "flow": {},
               "evidence_ids": [p["evidence_id"] for p in photos]}

    def stop(note):
        outcome["note"] = note
        return outcome

    record_id, record = mission_record_for_load(load_id)
    if record is None:
        return stop("No committed Mission Record is linked to this load, so no Customer Alert was sent.")

    # Joe Updates Mission Visibility: the evidence joins the Mission Record history.
    data = sandbox._load()
    stored = data.get(record_id) or {}
    stored.setdefault("events", []).append({
        "action": "mission_evidence_added", "via": "JOE", "timestamp": now, "load_id": load_id,
        "evidence": [{"evidence_id": p["evidence_id"], "type": p["evidence_type"]} for p in photos]})
    data[record_id] = stored
    sandbox._save(data)
    outcome["flow"]["joe"] = {"mission_visibility": "UPDATED"}

    def finish(result):
        data = sandbox._load()
        data[record_id].setdefault("customer_alerts", []).append(result)
        sandbox._save(data)
        return result

    # Joe Evaluates Communication Requirements.
    access = stored.get("portal_access") or {}
    channel, to = customer_contact(stored)
    requested_for = access.get("requested_for")
    reason = (None if access.get("pin") in ("CREATED", "ALREADY_PRESENT") else
              "the customer has no Mission Visibility Key for this mission")
    reason = reason or (None if channel else "there is no customer email or phone number on file")
    reason = reason or (None if requested_for else "no Operations person is on record for this mission's Mission Visibility")
    outcome["flow"]["joe"]["communication_required"] = reason is None
    if reason:
        return finish(stop(f"The photos are in the Mission Visibility View; no Customer Alert was sent: {reason}."))

    labels = sorted({p["label"] for p in photos})
    number = load_number(stored)
    link = customer_portal_link(url_root)
    kinds = ", ".join(l.lower() + "s" for l in labels)
    if channel == "text" and link:
        body = f"Level 1 Transport: new {kinds} for load {number} are in your Customer Portal: {link}"
    elif channel == "text":
        body = (f"Level 1 Transport: new {kinds} for load {number} were taken and are kept with your "
                f"mission record. Reply and we will send them.")
    else:
        body = render_template(EVIDENCE_ALERT_TEMPLATE, customer=brief._record_value(stored, "customer"),
                               load_number=number, labels=labels, count=len(photos), portal_url=link)
    sent = _publish_route_send(
        outcome, dict(stored, id=record_id), trigger=comi_routing.MISSION_EVIDENCE_ADDED, template="evidence_alert",
        to=to, subject=f"Level 1 Transport - Load {number}: {', '.join(labels)}", body=body,
        trigger_reason="Customer-facing mission evidence was added", requested_for=requested_for,
        action_type=publisher.MISSION_EVIDENCE_ALERT_ACTION_TYPE, auto_send_basis=publisher.MISSION_EVIDENCE_AUTO_SEND,
        mail_connector=mail_connector, channel=channel)
    if not sent["sent"]:
        return finish(stop(f"The photos are in the Mission Visibility View, but the Customer Alert to "
                           f"{', '.join(outcome['to'])} did not go out: {sent['detail']}."))
    return finish(stop(f"Customer Alert sent to {', '.join(outcome['to'])}."))
