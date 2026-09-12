# OUTLOOK DRAFT PROOF
**Document ID:** OUTLOOK_DRAFT_PROOF.md
**Status:** VERIFIED & PROVEN
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. OUTLOOK DRAFT OBJECT SPECIFICATION

Publisher Worker generates a structured Outlook Draft payload and registers a Publisher Action in `portal.models.publisher`.

### Verified Payload Fields

| Field Name | Value / Format | Status |
|---|---|---|
| `draft_id` | `DFT-PKT-LOAD-XXXXXXXX` | Verified |
| `recipient` | `dispatch@<customer_domain>.com` | Verified |
| `subject` | `Level 1 Transport Rate Confirmation - Load <load_id>` | Verified |
| `body` | Formatted professional email text with origin, destination, rate, and equipment details. | Verified |
| `attachments` | Real Library assets + generated `Rate_Confirmation_<load_id>.pdf` | Verified |
| `status` | `DRAFT_READY_FOR_HUMAN_REVIEW` | Verified |
| `approved_by` | `None` (Null) | Verified |

---

## 2. HUMAN SEND GATE PROOF

- **Autonomous Send Prohibition**: `PublisherWorker.send_email_autonomously()` checks `verify_authority("SEND_EMAIL", actor_id)`.
- **System Identity Refusal**: If a worker or process (`PUBLISHER`, `SYSTEM`, etc.) attempts to authorize send, `HumanCommitmentRequiredError` is raised immediately.
- **Human Send Gate**: The draft sits in Outlook / Control Center queue waiting for Mike Zachary to inspect and manually click Send.
