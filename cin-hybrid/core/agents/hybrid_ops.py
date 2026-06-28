from core.agents.hybrid_lifecycle_controller import HybridLifecycleController
from core.utils.logger import log

class HybridOps:
    """
    Operational engine for packet generation, correction, signature,
    and final submission. Now wired to HybridLifecycleController.
    """

    def __init__(
        self,
        data_source_client,
        email_client,
        packet_builder,
        pdf_edit_bridge=None,
    ):
        self.data_source_client = data_source_client
        self.email_client = email_client
        self.packet_builder = packet_builder
        self.pdf_edit_bridge = pdf_edit_bridge

        # NEW: lifecycle controller
        self.lifecycle = HybridLifecycleController()

        log("HybridOps initialized with lifecycle controller")

    def run_for_opportunity(self, vendor_id: str):
        """
        Full operational workflow:
        - Load vendor
        - Build packet
        - Pause for review
        """

        vendor = self.data_source_client.load_vendor(vendor_id)
        packet = {
            "vendor_id": vendor_id,
            "vendor": vendor,
            "status": "loaded",
            "version": 1,
        }

        self.lifecycle.on_loaded()

        packet = self.packet_builder.build(packet)
        packet["status"] = "generated"

        self.lifecycle.on_generated()

        packet["status"] = "awaiting_review"
        self.lifecycle.on_review()

        return packet

    def send_packet_to_docusign(self, packet, signer_email, signer_name):
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        self.lifecycle.on_external_edit_requested()

        packet = self.pdf_edit_bridge.send_to_docusign(
            packet,
            signer_email=signer_email,
            signer_name=signer_name,
        )

        self.lifecycle.on_external_edit_in_progress()

        return packet

    def wait_for_docusign(self, packet):
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        packet = self.pdf_edit_bridge.wait_for_completion(packet)

        self.lifecycle.on_external_edit_completed()

        return packet

    def retrieve_signed_packet(self, packet):
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        packet = self.pdf_edit_bridge.retrieve_from_docusign(packet)

        self.lifecycle.on_external_edit_completed()

        return packet

    def submit_packet(self, packet):
        packet["status"] = "submitted"
        self.email_client.send_packet(packet)

        self.lifecycle.on_submitted()

        return packet
