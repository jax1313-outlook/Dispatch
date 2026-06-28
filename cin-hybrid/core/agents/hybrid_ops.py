from core.utils.logger import log
from core.intel.hybrid_intelligence import HybridIntelligence


class HybridOps:
    """
    HybridOps: operational engine for Hybrid (your definition).
    - pulls vendor data (from sources you wire in)
    - runs HybridIntelligence
    - prepares application packet skeletons
    - triggers notification + next-step actions (to be extended)
    """

    def __init__(self, data_source_client=None, email_client=None, packet_builder=None):
        """
        data_source_client: abstraction over SAM.gov / vendor site / local data
        email_client: abstraction over your email notification system
        packet_builder: abstraction over application packet assembly
        """
        self.intel = HybridIntelligence()
        self.data_source_client = data_source_client
        self.email_client = email_client
        self.packet_builder = packet_builder

    def fetch_vendor_profile(self, vendor_id: str) -> dict:
        """
        Pulls raw vendor data from your chosen source.
        For now, this is a stub you can wire to:
        - SAM.gov API
        - scraped vendor site
        - local JSON/YAML
        """
        log(f"HybridOps.fetch_vendor_profile: vendor_id={vendor_id}")

        if not self.data_source_client:
            # Temporary stub: replace with real data source
            return {
                "vendor_id": vendor_id,
                "name": "Example Vendor",
                "sam_status": "active",
                "naics": ["541512"],
                "cage": "EX123",
                "duns": "000000000",
                "contracts_history": [],
                "cyber_posture": {},
                "contacts": [],
            }

        return self.data_source_client.get_vendor_profile(vendor_id)

    def build_intel_for_vendor(self, vendor_id: str) -> dict:
        """
        Full chain:
        - fetch vendor profile
        - run HybridIntelligence
        - return unified intelligence product
        """
        log(f"HybridOps.build_intel_for_vendor: vendor_id={vendor_id}")

        vendor_profile = self.fetch_vendor_profile(vendor_id)
        intel_product = self.intel.build(vendor_profile)

        return {
            "vendor_profile": vendor_profile,
            "intel": intel_product,
        }

    def prepare_application_packet(self, vendor_id: str, opportunity_id: str) -> dict:
        """
        Prepares a skeleton application packet (minus signatures).
        For now:
        - builds intel
        - returns a structured packet dict
        Later:
        - integrate packet_builder to generate PDFs/forms.
        """
        log(
            f"HybridOps.prepare_application_packet: "
            f"vendor_id={vendor_id}, opportunity_id={opportunity_id}"
        )

        intel_bundle = self.build_intel_for_vendor(vendor_id)
        vendor_profile = intel_bundle["vendor_profile"]
        intel = intel_bundle["intel"]

        packet = {
            "vendor_id": vendor_id,
            "opportunity_id": opportunity_id,
            "vendor_profile": vendor_profile,
            "intel": intel,
            "forms": [],          # to be populated by packet_builder
            "attachments": [],    # docs, certifications, etc.
            "status": "draft",
        }

        if self.packet_builder:
            packet = self.packet_builder.build(packet)

        return packet

    def notify_next_steps(self, packet: dict, recipient_email: str) -> None:
        """
        Sends a simple notification about next steps for a packet.
        For now:
        - logs the action
        - if email_client exists, sends a basic message
        """
        log(
            f"HybridOps.notify_next_steps: "
            f"packet_opportunity={packet.get('opportunity_id')}, "
            f"recipient={recipient_email}"
        )

        if not self.email_client:
            # Stub: you can wire this to your real email system later.
            log("HybridOps.notify_next_steps: email_client not configured, skipping send")
            return

        subject = f"Hybrid packet ready: {packet.get('opportunity_id')}"
        body = (
            f"Hybrid has prepared a draft application packet.\n\n"
            f"Vendor: {packet.get('vendor_id')}\n"
            f"Opportunity: {packet.get('opportunity_id')}\n"
            f"Status: {packet.get('status')}\n\n"
            f"Next steps: review, add signatures, and submit."
        )

        self.email_client.send_email(
            to=recipient_email,
            subject=subject,
            body=body,
        )

    def run_for_opportunity(self, vendor_id: str, opportunity_id: str, recipient_email: str):
        """
        High-level operational entrypoint:
        - build intel
        - prepare packet
        - notify next steps
        - return packet
        """
        log(
            f"HybridOps.run_for_opportunity: "
            f"vendor_id={vendor_id}, opportunity_id={opportunity_id}"
        )

        packet = self.prepare_application_packet(vendor_id, opportunity_id)
        self.notify_next_steps(packet, recipient_email)
