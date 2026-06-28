import requests
from core.utils.logger import log


class OutlookEmailClient:
    """
    Real Outlook email client using Microsoft Graph API.
    Requires:
    - Azure App Registration
    - Client ID
    - Tenant ID
    - Client Secret (for client credential flow)
    """

    def __init__(self, client_id: str, tenant_id: str, client_secret: str):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        self.token = None

        log("OutlookEmailClient initialized")

    def _get_token(self):
        """
        OAuth2 client credential flow.
        Retrieves a bearer token for Microsoft Graph.
        """
        log("OutlookEmailClient: requesting OAuth token")

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }

        response = requests.post(url, data=data)
        response.raise_for_status()

        token = response.json()["access_token"]
        self.token = token
        return token

    def send_email(self, to: str, subject: str, body: str):
        """
        Sends an email using Microsoft Graph API.
        Matches HybridOps's expected interface.
        """
        log("OutlookEmailClient.send_email called")

        if not self.token:
            self._get_token()

        url = "https://graph.microsoft.com/v1.0/users/jax1313@outlook.com/sendMail"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": to}}
                ],
            },
            "saveToSentItems": "true",
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in (200, 202):
            log("OutlookEmailClient: email sent successfully")
        else:
            log(f"OutlookEmailClient: email send failed: {response.text}")
            response.raise_for_status()
