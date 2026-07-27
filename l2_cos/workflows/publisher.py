"""Publisher / Auto-Contact workflow (System Rule 4).

Fires once a load's overall IntelligenceScore reaches
`l2_cos.models.intelligence.PUBLISH_THRESHOLD` (90). This is the one
workflow in the pipeline that runs WITHOUT a human decision gate — the
score threshold is the approval, per Rule 4's "auto-contact" wording.

Builds the InquiryArtifacts packet from the carrier's on-file documents
(captured once — Rule 14, see l2_cos/intelligence_store.py) and, only when
that packet is complete, emails the outbound load inquiry to the broker's
contact address. An incomplete packet means real paperwork (insurance,
authority, etc.) is missing, so the workflow declines to send rather than
going out the door with a broken packet.
"""

from __future__ import annotations

from l2_cos import email_delivery
from l2_cos.models.intelligence import PUBLISH_THRESHOLD, BrokerIntelligence, InquiryArtifacts
from l2_cos.models.state import Load

# Field name -> human-readable label, in the order System Rule 4 lists them.
_ARTIFACT_LABELS = {
    "business_card": "Business Card",
    "w9": "W-9",
    "insurance": "Insurance",
    "authority": "Authority",
    "rate_sheet": "Rate Sheet",
    "terms": "Terms",
    "rate_confirmation_package": "Rate Confirmation Package",
}


def is_triggered(score: int) -> bool:
    return score >= PUBLISH_THRESHOLD


def build_artifacts(carrier_documents: InquiryArtifacts | None) -> InquiryArtifacts:
    """The carrier's on-file document packet, or an all-missing packet if
    none was supplied (e.g. intelligence_store found no carrier_documents.json)."""
    return carrier_documents if carrier_documents is not None else InquiryArtifacts()


def _missing_labels(artifacts: InquiryArtifacts) -> list[str]:
    return [label for field, label in _ARTIFACT_LABELS.items() if not getattr(artifacts, field)]


def _inquiry_email(
    load: Load, raw_load: dict, broker: BrokerIntelligence | None, artifacts: InquiryArtifacts
) -> tuple[str, str]:
    broker_name = broker.company_name if broker else (load.broker_id or "the broker")
    lane = f"{raw_load.get('origin')} -> {raw_load.get('destination')}"
    subject = f"[L2-COS] Load inquiry — {load.load_id} ({lane})"

    checklist = "\n".join(f"  [x] {label}" for label in _ARTIFACT_LABELS.values())
    body = "\n".join(
        [
            f"Load        : {load.load_id}",
            f"Lane        : {lane}",
            f"Equipment   : {raw_load.get('equipment_type')}",
            f"Rate/mile   : {raw_load.get('rate_per_mile')}",
            f"Broker      : {broker_name}",
            f"Intelligence score: {load.intelligence_score} (>= {PUBLISH_THRESHOLD})",
            "",
            "Attached with this inquiry:",
            checklist,
        ]
    )
    return subject, body


def trigger(
    load: Load,
    raw_load: dict,
    broker: BrokerIntelligence | None,
    carrier_documents: InquiryArtifacts | None,
) -> dict:
    """Run the publisher workflow; return a result record.

    Declines to send (`sent: False`) without emailing anything if the
    artifacts packet is incomplete.
    """
    artifacts = build_artifacts(carrier_documents)
    if not artifacts.is_complete():
        return {
            "sent": False,
            "reason": f"inquiry artifacts incomplete: {', '.join(_missing_labels(artifacts))}",
            "artifacts": artifacts.model_dump(),
        }

    subject, body = _inquiry_email(load, raw_load, broker, artifacts)
    to = [broker.contact_email] if (broker and broker.contact_email) else [email_delivery.fallback_broker_address()]
    email_status = email_delivery.send(subject, body, to, fallback_id=f"{load.load_id}-inquiry")

    return {
        "sent": True,
        "email_status": email_status,
        "artifacts": artifacts.model_dump(),
        "recipients": to,
    }
