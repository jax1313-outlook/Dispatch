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
    securement_photo          the customer is told
    freight_condition_photo   the customer is told
    document                  filed, nothing announced

**A label on a button is a classification, not a second path.** The cockpit
still shows separate tiles, because a driver at a dock with gloves on taps one
thing rather than working a dropdown -- but every tile posts to the same route
and lands here. One operation, one set of refusals, one place to add the next
classification.
"""

from __future__ import annotations

from flask import flash, session

from portal.driver_actions import ERROR, SUCCESS, WARNING
from portal.models import sandbox

#: What each classification is called where a person reads it, and whether it
#: may arrive as several files at once.
CLASSIFICATIONS = {
    "pod": {"label": "Signed POD", "many": False},
    "bol": {"label": "Signed BOL", "many": False},
    "securement_photo": {"label": "Load securement photo", "many": True},
    "freight_condition_photo": {"label": "Freight condition photo", "many": True},
    "document": {"label": "Document", "many": True},
}


def classifications():
    """For a screen that wants to offer them. Ordered as a run happens."""
    return [(k, CLASSIFICATIONS[k]["label"]) for k in
            ("bol", "pod", "securement_photo", "freight_condition_photo", "document")]


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
    if classification in ("securement_photo", "freight_condition_photo"):
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
        report = closing_packet.build(
            record,
            today=clock.home_date().isoformat(),
            driver_name=str(session.get("driver_name") or ""),
            # The load row says `completed`, which it reaches only through
            # delivery. Read, not assumed.
            delivered=True)
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
