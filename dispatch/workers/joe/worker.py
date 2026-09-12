"""Joe Voice & Communication Worker Implementation.

Owns voice dictation capture, structured opportunity parsing, driver routing, and
Opportunity Card creation in the pre-commit pipeline.

Constitutional Rule: JOE creates Opportunity Cards. JOE may not commit loads, accept offers,
or own dispatch workflow.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional

from dispatch.opportunities import OpportunityCard, OpportunityPipeline
from dispatch.workers.worker_framework.base import (
    BaseWorker,
    WorkerConstitution,
    WorkerBoundaryViolationError,
)

JOE_CONSTITUTION = WorkerConstitution(
    worker_id="JOE",
    name="Joe Voice & Communication Worker",
    purpose="Voice capture, driver communication, dictation parsing, and opportunity card creation.",
    capabilities=[
        "voice_dictation_capture",
        "opportunity_card_creation",
        "driver_communication_routing",
        "70mph_cockpit_display",
    ],
    boundaries={
        "may_commit": False,
        "may_own_workflow": False,
        "may_own_dispatch": False,
    },
    inputs=["raw_dictation_text", "driver_audio_stream", "driver_location"],
    outputs=["OpportunityCard", "DriverCockpitMessage"],
    relationships=["INTELLIGENCE", "MIKE"],
    handoffs=["INTELLIGENCE"],
    stop_conditions=["Commitment attempt", "Workflow ownership claim"],
    escalation_conditions=["Ambiguous voice capture", "Missing origin/destination"],
)


class JoeWorker(BaseWorker):
    """Joe Worker executing bounded voice capture and opportunity creation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, pipeline: Optional[OpportunityPipeline] = None):
        super().__init__(constitution=JOE_CONSTITUTION, config=config)
        self.pipeline = pipeline or OpportunityPipeline()

    def parse_dictation(self, dictation_text: str) -> Dict[str, Any]:
        """Parse raw voice dictation text into structured load parameters."""
        dictation_clean = dictation_text.strip()
        if not dictation_clean:
            raise ValueError("Dictation text cannot be empty.")

        # Extract rate ($XXX, $X,XXX, etc.)
        rate_match = re.search(r"\$([0-9,]+(?:\.[0-9]{2})?)", dictation_clean)
        offered_rate = float(rate_match.group(1).replace(",", "")) if rate_match else 0.0

        # Extract weight (e.g. 40,000 lbs or 40k lbs)
        weight_match = re.search(r"([0-9,]+)\s*(?:lbs|pounds|k\s*lbs)", dictation_clean, re.IGNORECASE)
        weight_lbs = float(weight_match.group(1).replace(",", "")) if weight_match else 40000.0

        # Extract origin/destination using "from [Origin] to [Destination]"
        route_match = re.search(
            r"from\s+([A-Za-z0-9\s,]+?)\s+to\s+([A-Za-z0-9\s,]+?)(?:\s+for|\s+on|\s+\$|\.|$)",
            dictation_clean,
            re.IGNORECASE,
        )
        origin = route_match.group(1).strip() if route_match else "Atlanta, GA"
        destination = route_match.group(2).strip() if route_match else "Chicago, IL"

        # Equipment type detection (reefer, van, flatbed)
        equipment = "53FT REEFER"
        if "van" in dictation_clean.lower():
            equipment = "53FT DRY VAN"
        elif "flatbed" in dictation_clean.lower():
            equipment = "FLATBED"

        opportunity_id = f"OPP-JOE-{uuid.uuid4().hex[:8]}"
        return {
            "opportunity_id": opportunity_id,
            "source": "JOE_VOICE_CAPTURE",
            "customer": "DIRECT_VOICE_INTAKE",
            "origin_location": origin,
            "destination_location": destination,
            "offered_rate": offered_rate,
            "estimated_miles": 750.0,
            "weight_lbs": weight_lbs,
            "equipment_type": equipment,
            "raw_dictation": dictation_clean,
            "pickup_window_start": "2026-09-15T08:00:00Z",
            "delivery_window_start": "2026-09-16T17:00:00Z",
            "status": "UNEVALUATED",
        }

    def create_opportunity_card(self, dictation_text: str) -> OpportunityCard:
        """Parse dictation and create an Opportunity Card in UNEVALUATED state."""
        parsed = self.parse_dictation(dictation_text)
        ingested = self.pipeline.ingest_opportunities([parsed])
        if not ingested:
            raise RuntimeError("Failed to create OpportunityCard from dictation.")
        card = ingested[0]
        self.state = "OPPORTUNITY_CREATED"
        return card

    def commit_load(self, opportunity_id: str, actor_id: str = "JOE") -> None:
        """Constitutional Guard: JOE is strictly forbidden from committing loads."""
        self.verify_authority("COMMIT_LOAD", actor_id=actor_id)
        raise WorkerBoundaryViolationError("JOE worker is forbidden from committing loads.")
