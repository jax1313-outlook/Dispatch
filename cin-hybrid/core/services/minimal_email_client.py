from core.utils.logger import log


class MinimalEmailClient:
    """
    Minimal stub email client.
    Replace with:
    - Outlook Graph API
    - SMTP
    - Microsoft 365 integration
    """

    def __init__(self):
        log("MinimalEmailClient initialized")

    def send_email(self, to: str, subject: str, body: str):
        log("MinimalEmailClient.send_email called")
        log(f"TO: {to}")
        log(f"SUBJECT: {subject}")
        log(f"BODY:\n{body}")
        log("Email send simulated (no real email sent)")
