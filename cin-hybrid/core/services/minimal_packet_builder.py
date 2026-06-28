from core.utils.logger import log


class MinimalPacketBuilder:
    """
    Minimal stub packet builder.
    Replace with:
    - PDF generator
    - form filler
    - document assembler
    """

    def __init__(self):
        log("MinimalPacketBuilder initialized")

    def build(self, packet: dict) -> dict:
        log("MinimalPacketBuilder.build called")

        # Add placeholder forms
        packet["forms"] = [
            {"form_name": "Vendor Info Form", "status": "generated"},
            {"form_name": "Opportunity Cover Sheet", "status": "generated"},
        ]

        # Add placeholder attachments
        packet["attachments"] = [
            {"filename": "sam_registration.pdf", "status": "attached"},
            {"filename": "capability_statement.pdf", "status": "attached"},
        ]

        packet["status"] = "packet_generated"

        return packet
