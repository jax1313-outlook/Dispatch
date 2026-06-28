from core.utils.logger import log
import requests
import os
import base64


class OutlookEmailClient:
    """
    Real Outlook Graph email client.
    HybridOps expects: send_packet(packet)
    """

    def __init__(self, graph_token: str, from_address: str):
        self.graph_token = graph_token
        self.from_address = from_address

        log("OutlookEmailClient initialized")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.graph_token}",
            "Content-Type": "application/json"
        }

    def send_packet(self, packet: dict):
        """
        HybridOps entrypoint.
        Sends the final packet PDF via Outlook Graph.
        """

        vendor_id = packet.get("vendor_id")
        pdf_path = packet.get("pdf_path")

        if not pdf_path or not os.path.exists(pdf_path):
            raise RuntimeError(f"Packet PDF not found: {pdf_path}")

        subject = f"Completed Packet Submission - {vendor_id}"
        body = f"Attached is the completed, signed packet for vendor {vendor_id}."

        # Read PDF and encode
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": self.from_address}}
                ],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(pdf_path),
                        "contentBytes": pdf_b64
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        url = f"https://graph.microsoft.com/v1.0/users/{self.from_address}/sendMail"

        log(f"Submitting packet for vendor {vendor_id} via Outlook Graph")

        resp = requests.post(url, headers=self._headers(), json=message)

        if resp.status_code not in (200, 202):
            log(f"Packet submission failed: {resp.status_code} {resp.text}")
            raise RuntimeError("Failed to submit packet via Outlook Graph")

        log("Packet submitted successfully")
        return True
