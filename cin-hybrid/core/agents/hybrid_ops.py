from core.utils.logger import log

class HybridOps:
    """
    Operational engine for packet generation, correction, signature,
    and final submission. Now includes DocuSignBridge as the fourth
    real service client.
    """

    def __init__(
        self,
        data_source_client,
        email_client,
        packet_builder,
        pdf_edit_bridge=None,   # NEW
    ):
        self.data_source_client = data_source_client
        self.email_client = email_client
        self.packet_builder = packet_builder
        self.pdf_edit_bridge = pdf_edit_bridge

        log("HybridOps initialized with data, email, packet, and DocuSign services")

    def run_for_opportunity(self, vendor_id: str):
        """
        Full operational workflow:
        - Load vendor
        - Build packet
        - Pause for review
        - Optional DocuSign correction/signature loop
        - Final submission
        """

        # 1. Load vendor
        vendor = self.data_source_client.load_vendor(vendor_id)
        packet = {
            "vendor_id": vendor_id,
            "vendor": vendor,
            "status": "loaded",
            "version": 1,
        }
        log(f"Vendor loaded: {vendor_id}")

        # 2. Build packet PDF
        packet = self.packet_builder.build(packet)
        packet["status"] = "generated"
        log(f"Packet generated for vendor {vendor_id}")

        # 3. Pause for human review
        packet["status"] = "awaiting_review"
        log("Packet awaiting human review")

        return packet

    def send_packet_to_docusign(self, packet, signer_email, signer_name):
        """
        Trigger the external edit + signature loop.
        """
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        packet["status"] = "awaiting_external_edit"
        log("Packet paused for external edit/signature")

        # 4. Send to DocuSign
        packet = self.pdf_edit_bridge.send_to_docusign(
            packet,
            signer_email=signer_email,
            signer_name=signer_name,
        )
        log("Packet sent to DocuSign")

        return packet

    def wait_for_docusign(self, packet):
        """
        Poll DocuSign until envelope is completed.
        """
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        packet = self.pdf_edit_bridge.wait_for_completion(packet)
        log("DocuSign envelope completed")

        return packet

    def retrieve_signed_packet(self, packet):
        """
        Pull corrected + signed PDF back into HybridOps.
        """
        if not self.pdf_edit_bridge:
            raise RuntimeError("DocuSignBridge not configured")

        packet = self.pdf_edit_bridge.retrieve_from_docusign(packet)
        log("Corrected + signed packet retrieved")

        return packet

    def submit_packet(self, packet):
        """
        Final submission via OutlookEmailClient.
        """
        packet["status"] = "submitted"
        self.email_client.send_packet(packet)
        log("Packet submitted")

        return packet
