"""One way to put a document on a Mission Record.

**MISSION ARTIFACT ATTACHMENT RULE, Mike Zachary, 2026-09-16:**

    The answer should always be: Mission Record -> Attach Artifact.
    Everything else is classification.

Before this there were three attach routes -- `cockpit_pod` and `cockpit_photos`
twice -- each with its own handler, its own refusals and its own consequences,
and **no way at all to attach a Bill of Lading**, which is the controlling
freight document. Asked "where do I attach this?", the build had three answers
and one shrug.

    Federal BOL = controlling freight document.
        -- PUBLISHER TEST RULING, REVISION 3

So: one operation. What varies is the **classification**, and a classification
carries its own consequence because the consequence is what the classification
*means*:

    pod                       the run is finished (a POD completes the load and
                              triggers the closing packet, 2026-09-16)
    bol                       the controlling freight document, filed
    loaded_vehicle_photo      the customer is told
    securement_photo          the customer is told
    final_condition_photo     the customer is told
    document                  filed, nothing announced

**The three photo names are his**, and the same three everywhere: *"Publisher,
Cockpit, Mission Record, and Placeholder Registry must use the same three
names."* This module carried the old two-name list until 2026-09-17, so there
was no way to upload a Loaded Vehicle photo at all, and the tile offering
"Freight Condition" was a concept he had already struck.

**A label on a button is a classification, not a second path.** The cockpit
still shows separate tiles, because a driver at a dock with gloves on taps one
thing rather than working a dropdown -- but every tile posts to the same route
and lands here. One operation, one set of refusals, one place to add the next
classification.
"""

from __future__ import annotations

from flask import flash, session

from pathlib import Path

from portal.driver_actions import ERROR, SUCCESS, WARNING
from portal.models import sandbox

#: What each classification is called where a person reads it, and whether it
#: may arrive as several files at once.
CLASSIFICATIONS = {
    "pod": {"label": "Signed POD", "many": False},
    "bol": {"label": "Signed BOL", "many": False},
    "loaded_vehicle_photo": {"label": "Photos - Loaded Vehicle", "many": True},
    "securement_photo": {"label": "Photos - Mid-Route Securement", "many": True},
    "final_condition_photo": {"label": "Photos - Final Condition", "many": True},
    "document": {"label": "Document", "many": True},
}

#: The photo classifications, which share one consequence: the customer is told.
PHOTO_CLASSIFICATIONS = ("loaded_vehicle_photo", "securement_photo",
                         "final_condition_photo")


def classifications():
    """For a screen that wants to offer them. Ordered as a run happens."""
    return [(k, CLASSIFICATIONS[k]["label"]) for k in
            ("bol", "pod", "loaded_vehicle_photo", "securement_photo",
             "final_condition_photo", "document")]


def attach(load_id: str, classification: str, uploads, actor: str, *,
           mail_connector=None, url_root: str = "") -> tuple[str, str]:
    """Attach one or more artifacts to a Mission Record. **The one path.**

    Returns (message, category) like every other driver action: a tap that
    produces a silent redirect is indistinguishable from a tap that worked.
    """
    from portal import driver_actions

    classification = (classification or "").strip()
    if classification not in CLASSIFICATIONS:
        return ("That is not an artifact type. Pick what the document is.", ERROR)

    spec = CLASSIFICATIONS[classification]
    uploads = [f for f in (uploads or []) if f and getattr(f, "filename", "")]
    if not uploads:
        # Names what was expected. "No file was attached" is true of every
        # tile; a driver who taps the wrong one needs to be told which.
        return "No %s was attached." % spec["label"].lower(), ERROR

    if not spec["many"] and len(uploads) > 1:
        return ("%s is one document. Attach them one at a time."
                % spec["label"], ERROR)

    # The consequence belongs to the classification, so it is chosen here and
    # applied by the handler that owns it -- not re-implemented per route.
    if classification == "pod":
        said = driver_actions.upload_pod(load_id, uploads[0], actor)
        # **The packet follows the POD, not the route.** It used to be built by
        # the cockpit's handler, so the parked Driver Portal's POD route
        # completed a run and filed nothing.
        build_closing_packet(load_id)
        return said
    if classification in PHOTO_CLASSIFICATIONS:
        return driver_actions.upload_mission_photos(
            load_id, classification, uploads, actor,
            mail_connector=mail_connector, url_root=url_root)
    return _file_it(load_id, classification, uploads, actor)


def _file_it(load_id: str, classification: str, uploads, actor: str) -> tuple[str, str]:
    """Attach and say so. **Nothing goes out.**

    A Bill of Lading and a loose document are evidence, not an announcement.
    The BOL is the controlling freight document and belongs on the record the
    moment it is signed; telling a customer about it is a different act with a
    different owner.
    """
    from dispatch import services as dispatch_svc

    label = CLASSIFICATIONS[classification]["label"]
    filed = 0
    for upload in uploads:
        data = upload.read()
        if not data:
            return "That file came through empty. Try again.", ERROR
        try:
            dispatch_svc.attach_evidence(
                load_id, evidence_type=classification, description=label,
                file_data=data, original_filename=upload.filename,
                uploaded_by="driver:%s" % actor)
        except ValueError as exc:
            return str(exc), ERROR
        filed += 1

    return ("%s attached to the Mission Record." % label if filed == 1
            else "%d %ss attached to the Mission Record." % (filed, label.lower()),
            SUCCESS)


# ---- The closing packet -------------------------------------------------
#
# **It lives with the act, not with a route.** It used to sit in
# `portal/routes/joe_portal.py`, so the parked Driver Portal's own POD route
# completed a run and **filed nothing** -- the same dead end the regression
# audit found on the cockpit, surviving on the other screen because the
# consequence belonged to a handler instead of to what happened. BATCH 8.


def build_closing_packet(record_id: str) -> dict | None:
    """File a **completed** load's documents under its load number.

    **Keyed on what happened, not on which button was pressed.** An earlier
    version fired on the `pod_received` event without looking at the result, so
    a refused transition still produced a packet -- and passed `delivered=True`
    unconditionally, printing "Delivered" on a customer-facing document for a
    load that never delivered. Found by the regression audit, 2026-09-16. The
    load row is the authority on whether the run finished; this reads it.

    **Built once.** A load that already has a packet is left alone, so pressing
    a milestone again does not rewrite documents that may already have gone out.

    **It never costs the run.** A driver who has delivered his freight and sent
    his POD has finished, whether or not a Word template was reachable. What
    went wrong is flashed and recorded; the completion stands either way.
    """
    from dispatch import closing_packet, clock
    from dispatch import services as dispatch_svc

    load = dispatch_svc.get_load(record_id)
    if not load or load.get("status") != "completed":
        return None
    record = sandbox.get(record_id)
    if not record or record.get("closing_packet"):
        return None
    try:
        bundle = dispatch_svc.get_load_bundle(record_id) or {}
        report = closing_packet.build(
            record,
            today=clock.home_date().isoformat(),
            driver_name=str(session.get("driver_name") or ""),
            # What was actually scanned and uploaded, so the covers state what
            # is in the packet rather than what somebody ticked at a dock.
            evidence=bundle.get("evidence") or [],
            # **Not the dock forms, and not the onboarding policy.** 05 and 03
            # are produced at their stops and reach the packet as the scanned
            # signed copies; generating fresh blanks here would put the wrong
            # document in front of a factor. See `_NOT_IN_THE_CLOSING_PACKET`.
            without=closing_packet._NOT_IN_THE_CLOSING_PACKET)
    except Exception as exc:  # noqa: BLE001 - a packet is never worth a 500 in a cab
        flash("The closing packet could not be built: %s" % exc)
        return None

    if report["ok"]:
        flash("Closing packet filed under %s: %d document%s."
              % (report["load_number"] or "no load number",
                 len(report["documents"]),
                 "" if len(report["documents"]) == 1 else "s"))
    else:
        flash("Closing packet: %s" % (report["note"] or "some documents failed."))

    data = sandbox._load()
    stored = data.get(record_id)
    if stored is not None:
        # What was produced and what is still unanswered, kept with the record
        # so the packet can be read back without rebuilding it.
        stored["closing_packet"] = report
        data[record_id] = stored
        sandbox._save(data)
    return report


# ---- The paper a driver carries in ---------------------------------------
#
# **Generation at activation, printing at arrival.** Owner, 2026-09-17:
#
#     "the truck is parked and stored at a location miles away. The driver
#      begins ELD, pre-trip inspection, fuels along the way. at some point the
#      activation of pickup is done and Publisher creates load documents and
#      ques for printing upon arrival at pickup location. Driver prints,
#      clipboards them and enters."
#
# So Dispatch's whole job is to have the email sitting there before he needs
# it. There is no PRINT control and there should not be one: he prints in the
# cab, from Outlook, to the printer in the truck. Asked how that works, he was
# plain -- *"done it for years ... it can open emails with attachments and send
# to a local API connected printer. no browser is used."*
#
# The two triggers are milestones that already exist:
#
#     en_route_pickup   START RUN            -> the pickup form
#     departed_pickup   Rolling to delivery  -> the delivery form

#: Which milestone hands which stop's paper to the driver.
STOP_DOCUMENTS = {
    "en_route_pickup": "pickup",
    "departed_pickup": "delivery",
}

#: Where the driver's tablet reads its mail. The arrival notice already copies
#: the office here, so it is the mailbox this build knows about -- but which
#: mailbox the **tablet** opens is the Owner's to say, and this is the line to
#: change when he does.
DRIVER_MAILBOX = "Ops@l1truck.com"


def prepare_stop_documents(record_id: str, milestone: str, *,
                           mail_connector=None) -> dict | None:
    """Fill the form for this stop and put it in front of the driver.

    Returns the report, or None when this milestone is not one of the two that
    carry paper.

    **It never costs the run.** A driver who has started his run has started
    it, whether or not a Word template was reachable or Outlook was open. What
    went wrong is recorded on the mission; the milestone stands either way.
    """
    phase = STOP_DOCUMENTS.get(str(milestone or "").strip())
    if not phase:
        return None

    from dispatch import closing_packet, clock

    record = sandbox.get(record_id)
    if not record:
        return None

    folder = closing_packet.folder_for(
        record.get("load_number")
        or (record.get("card_data") or {}).get("load_id") or "") / phase
    try:
        report = closing_packet.build(
            record,
            out_dir=folder,
            today=clock.home_date().isoformat(),
            driver_name=str(session.get("driver_name") or ""),
            only=closing_packet.PHASE_SETS[phase])
    except Exception as exc:  # noqa: BLE001 - paper is never worth a 500 in a cab
        flash("The %s paperwork could not be prepared: %s" % (phase, exc))
        return None

    report["phase"] = phase
    report["sent"] = _send_to_the_cab(record, phase, report,
                                      mail_connector=mail_connector)

    data = sandbox._load()
    stored = data.get(record_id)
    if stored is not None:
        # Kept per stop, so the second does not overwrite the first and he can
        # see what was prepared for each end of the run.
        prepared = dict(stored.get("stop_documents") or {})
        prepared[phase] = report
        stored["stop_documents"] = prepared
        data[record_id] = stored
        sandbox._save(data)
    return report


def _send_to_the_cab(record: dict, phase: str, report: dict, *,
                     mail_connector=None) -> bool:
    """Email the filled form to the mailbox the tablet reads.

    Attachments, not a body: *"Doc files in folders emails with attachments."*
    He opens it in the cab, prints to the local printer, clipboards the paper.
    """
    documents = [d["output"] for d in report.get("documents") or []
                 if d.get("output")]
    if not documents or mail_connector is None:
        return False

    numbers = (record.get("numbers") or {})
    label = str(numbers.get("load_label") or record.get("load_number") or "").strip()
    subject = "%s paperwork%s" % (phase.title(), " - %s" % label if label else "")
    body = ("Print these before you go in.\n\n"
            + "\n".join("  - " + Path(d).name for d in documents))
    try:
        answer = mail_connector.send([DRIVER_MAILBOX], subject, body,
                                     attachments=documents)
    except Exception:  # noqa: BLE001 - a quiet mailbox must not cost the run
        return False
    return bool(answer.get("ok"))
