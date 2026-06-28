import os
import base64
import time
import requests
from core.utils.logger import log


class DocuSignBridge:
    """
    Bridge between HybridOps and DocuSign.

    Responsibilities:
    - Upload packet PDF to DocuSign as an envelope
    - Let user edit/sign in DocuSign UI
    - Poll for completion
    - Download corrected + signed PDF back into HybridOps
    """

    def __init__(
        self,
        base_path: str = "generated_packets",
        docusign_base_url: str = "https://demo.docusign.net/restapi/v2.1",
        account_id: str = "",
        auth_token: str = "",
    ):
        self.base_path = base_path
        self.docusign_base_url = docusign_base_url.rstrip("/")
        self.account_id = account_id
        self.auth_token = auth_token

        log(
            f"DocuSignBridge initialized "
            f"(base_path={self.base_path}, account_id={self.account_id})"
        )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def send_to_docusign(self, packet: dict, signer_email: str, signer_name: str) -> dict:
        """
        Creates a DocuSign envelope from the packet PDF.
        Returns updated packet with envelope_id and status.
        """
        log("DocuSignBridge.send_to_docusign called")

        pdf_path = packet.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Packet PDF not found: {pdf_path}")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        vendor_id = packet.get("vendor_id", "unknown_vendor")
        subject = f"Contract Application Packet - {vendor_id}"

        envelope_definition = {
            "emailSubject": subject,
            "documents": [
                {
                    "documentBase64": pdf_b64,
                    "name": f"{vendor_id}_packet.pdf",
                    "fileExtension": "pdf",
                    "documentId": "1",
                }
            ],
            "recipients": {
                "signers": [
                    {
                        "email": signer_email,
                        "name": signer_name,
                        "recipientId": "1",
                        "routingOrder": "1",
                        "tabs": {
                            # Minimal placeholder; you can add specific signature fields later
                            "signHereTabs": [
                                {
                                    "anchorString": "SIGN_HERE",
                                    "anchorUnits": "pixels",
                                    "anchorXOffset": "0",
                                    "anchorYOffset": "0",
                                }
                            ]
                        },
                    }
                ]
            },
            "status": "sent",
        }

        url = f"{self.docusign_base_url}/accounts/{self.account_id}/envelopes"
        resp = requests.post(url, headers=self._headers(), json=envelope_definition)

        if resp.status_code >= 300:
            log(f"DocuSign envelope creation failed: {resp.status_code} {resp.text}")
            raise RuntimeError("Failed to create DocuSign envelope")

        data = resp.json()
        envelope_id = data.get("envelopeId")
        log(f"DocuSign envelope created: {envelope_id}")

        packet["docusign_envelope_id"] = envelope_id
        packet["status"] = "external_edit_in_progress"

        return packet

    def wait_for_completion(self, packet: dict, poll_interval: int = 15, timeout: int = 1800) -> dict:
        """
        Polls DocuSign for envelope completion.
        Returns packet when envelope is completed or raises on timeout.
        """
        log("DocuSignBridge.wait_for_completion called")

        envelope_id = packet.get("docusign_envelope_id")
        if not envelope_id:
            raise ValueError("No DocuSign envelope_id on packet")

        url = f"{self.docusign_base_url}/accounts/{self.account_id}/envelopes/{envelope_id}"

        start = time.time()
        while True:
            resp = requests.get(url, headers=self._headers())
            if resp.status_code >= 300:
                log(f"DocuSign envelope status check failed: {resp.status_code} {resp.text}")
                raise RuntimeError("Failed to check DocuSign envelope status")

            data = resp.json()
            status = data.get("status")
            log(f"DocuSign envelope status: {status}")

            if status in ("completed", "voided", "declined"):
                packet["docusign_status"] = status
                break

            if time.time() - start > timeout:
                raise TimeoutError("DocuSign envelope did not complete in time")

            time.sleep(poll_interval)

        return packet

    def retrieve_from_docusign(self, packet: dict) -> dict:
        """
        Retrieves the corrected + signed PDF from DocuSign.
        Updates packet with new pdf_path, status, and version.
        """
        log("DocuSignBridge.retrieve_from_docusign called")

        envelope_id = packet.get("docusign_envelope_id")
        if not envelope_id:
            raise ValueError("No DocuSign envelope_id on packet")

        # Get document list
        docs_url = f"{self.docusign_base_url}/accounts/{self.account_id}/envelopes/{envelope_id}/documents"
        resp = requests.get(docs_url, headers=self._headers())
        if resp.status_code >= 300:
            log(f"DocuSign document list failed: {resp.status_code} {resp.text}")
            raise RuntimeError("Failed to list DocuSign documents")

        docs = resp.json().get("envelopeDocuments", [])
        if not docs:
            raise RuntimeError("No documents found in DocuSign envelope")

        # Assume first document is the signed packet
        doc_id = docs[0].get("documentId")

        download_url = f"{docs_url}/{doc_id}"
        resp = requests.get(download_url, headers=self._headers())
        if resp.status_code >= 300:
            log(f"DocuSign document download failed: {resp.status_code} {resp.text}")
            raise RuntimeError("Failed to download DocuSign document")

        vendor_id = packet.get("vendor_id", "unknown_vendor")
        corrected_path = os.path.join(self.base_path, f"{vendor_id}_packet_signed.pdf")

        with open(corrected_path, "wb") as f:
            f.write(resp.content)

        log(f"Corrected + signed PDF retrieved: {corrected_path}")

        packet["pdf_path"] = corrected_path
        packet["status"] = "ready_for_submission"
        packet["version"] = packet.get("version", 1) + 1

        return packet
