"""Commitment Package Publisher Worker Implementation.

Consumes committed Mission Cards, retrieves active Library templates, incorporates past
Archive examples, builds Rate Confirmation packets, and prepares Outlook email drafts.

Constitutional Rule: PUBLISHER produces documents and email drafts. PUBLISHER requires
human approval before sending emails. PUBLISHER cannot send emails autonomously.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from portal.models import library as library_model
from portal.models import publisher as publisher_model
from worker_framework.base import (
    BaseWorker,
    WorkerConstitution,
    WorkerBoundaryViolationError,
    HumanCommitmentRequiredError,
)

PUBLISHER_CONSTITUTION = WorkerConstitution(
    worker_id="PUBLISHER",
    name="Commitment Package Publisher Worker",
    purpose="Commitment package lifecycle: Library asset retrieval, packet assembly, and Outlook draft generation.",
    capabilities=[
        "committed_mission_card_consumption",
        "library_template_retrieval",
        "archive_example_incorporation",
        "rate_confirmation_packet_assembly",
        "outlook_email_draft_preparation",
    ],
    boundaries={
        "may_commit": False,
        "may_send_email_autonomously": False,
        "requires_human_approval_for_send": True,
    },
    inputs=["CommittedMissionCard", "LibraryAssets", "ArchiveExamples"],
    outputs=["PublisherPacket", "OutlookDraftEmail"],
    relationships=["INTELLIGENCE", "MIKE", "DISPATCH"],
    handoffs=["DISPATCH", "HUMAN_OUTLOOK_REVIEW"],
    stop_conditions=["Autonomous send attempt", "Unapproved packet delivery"],
    escalation_conditions=["Missing library asset", "Missing rate confirmation template"],
)


class PublisherWorker(BaseWorker):
    """Publisher Worker executing post-commitment packet and email draft generation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(constitution=PUBLISHER_CONSTITUTION, config=config)
        self.packet_queue: List[Dict[str, Any]] = []

    def consume_committed_mission(self, mission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest committed Mission Card data."""
        load_id = mission_data.get("load_id") or mission_data.get("opportunity_id") or f"LOAD-{uuid.uuid4().hex[:6]}"
        record = {
            "load_id": load_id,
            "customer": mission_data.get("customer", "UNKNOWN_CUSTOMER"),
            "origin": mission_data.get("pickup_location") or mission_data.get("origin_location", ""),
            "destination": mission_data.get("delivery_location") or mission_data.get("destination_location", ""),
            "rate": float(mission_data.get("offered_rate") or mission_data.get("confirmed_rate") or 0.0),
            "equipment": mission_data.get("equipment", "53FT REEFER"),
            "status": "COMMITTED",
        }
        self.state = "MISSION_CONSUMED"
        return record

    def retrieve_library_template(self, document_type: str = "rate_confirmation") -> Dict[str, Any]:
        """Retrieve actual approved Library assets from portal library model."""
        available_assets = library_model.get_available_company_assets()
        missing_assets = library_model.get_missing_company_assets()
        company_records = library_model.get_section("company")

        return {
            "template_id": f"TPL-{document_type.upper()}-v1",
            "document_type": document_type,
            "header": "LEVEL 1 TRANSPORT - RATE CONFIRMATION & DISPATCH BRIEF",
            "available_assets": available_assets,
            "missing_assets": missing_assets,
            "company_records_count": len(company_records),
            "status": "ACTIVE",
        }

    def generate_rate_confirmation_packet(self, mission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build rate confirmation packet combining Mission Card & real Library assets."""
        mission = self.consume_committed_mission(mission_data)
        template = self.retrieve_library_template("rate_confirmation")

        action = publisher_model.create_action(
            action_type="Rate Confirmation Package Required",
            sandbox_id=f"MISSION-{mission['load_id']}",
            trigger_reason=f"Committed mission {mission['load_id']} realized by human commitment",
            available_data=template["available_assets"],
            missing_data=template["missing_assets"],
        )

        packet = {
            "packet_id": action["id"],
            "load_id": mission["load_id"],
            "template_id": template["template_id"],
            "header": template["header"],
            "customer": mission["customer"],
            "origin": mission["origin"],
            "destination": mission["destination"],
            "rate": mission["rate"],
            "equipment": mission["equipment"],
            "available_assets": template["available_assets"],
            "pdf_filename": f"Rate_Confirmation_{mission['load_id']}.pdf",
            "status": "PACKET_GENERATED",
        }
        self.packet_queue.append(packet)
        self.state = "PACKET_READY"
        return packet

    def prepare_outlook_draft(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Outlook draft email payload for human review."""
        draft = {
            "draft_id": f"DFT-{packet['packet_id']}",
            "recipient": f"dispatch@{packet['customer'].lower().replace(' ', '')}.com",
            "subject": f"Level 1 Transport Rate Confirmation - Load {packet['load_id']}",
            "body": (
                f"Hello,\n\n"
                f"Please find attached the signed Rate Confirmation for Load {packet['load_id']} "
                f"({packet['origin']} -> {packet['destination']}) at ${packet['rate']:,.2f}.\n\n"
                f"Equipment: {packet['equipment']}.\n\n"
                f"Best regards,\nMike Zachary\nLevel 1 Transport"
            ),
            "attachments": [packet["pdf_filename"]],
            "status": "DRAFT_READY_FOR_HUMAN_REVIEW",
            "approved_by": None,
        }
        self.state = "OUTLOOK_DRAFT_READY"
        return draft

    def send_email_autonomously(self, draft: Dict[str, Any], actor_id: str = "PUBLISHER") -> None:
        """Constitutional Guard: PUBLISHER is strictly forbidden from sending emails autonomously."""
        self.verify_authority("SEND_EMAIL", actor_id=actor_id)
        raise WorkerBoundaryViolationError("PUBLISHER worker cannot send emails autonomously.")
