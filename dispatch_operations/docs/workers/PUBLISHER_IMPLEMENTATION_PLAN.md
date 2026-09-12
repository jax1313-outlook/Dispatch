# PUBLISHER WORKER IMPLEMENTATION PLAN
**Document ID:** 06_PUBLISHER_IMPLEMENTATION_PLAN.md / PUBLISHER_IMPLEMENTATION_PLAN.md
**Status:** BINDING IMPLEMENTATION PLAN
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. COMMITMENT PACKAGE LIFECYCLE & REASONING WORKER MODEL

The Publisher Worker owns the commitment package lifecycle. Publisher is not a simple mail merge engine; it is a reasoning worker that consumes committed Mission Cards, queries active templates from Library, incorporates historical examples from Archive, and produces rate confirmation packets and Outlook draft communications.

### Core Component Integrations
- **Module Path**: `dispatch operations/workers/publisher/worker.py` & `dispatch/workers/publisher/worker.py`
- **Integrations**:
  - `portal.models.publisher.PublisherQueue`
  - `portal.models.library.LibraryStore` / `reconciliation.adapters.library_adapter`
  - `portal.models.archive.ArchiveStore` / `reconciliation.adapters.archive_adapter`
  - `dispatch.connectors.outlook_connector.OutlookConnector`

---

## 2. PRODUCTION PIPELINE & OUTLOOK DRAFT INTEGRATION

### Production Pipeline
1. **Trigger**: Ingestion of `COMMITMENT_REALIZED` event naming a committed `Mission Card` (`load_id`).
2. **Library Asset Retrieval**: Query `library_adapter` for active Rate Confirmation and Dispatch Brief templates.
3. **Archive Comparison**: Inspect `archive_adapter` for past load records with same customer/broker to verify preferred terms or accessorial wording.
4. **Packet Production**: Generate complete Rate Confirmation packet data and PDF representation.
5. **Outlook Draft Generation**:
   - Construct professional email body referencing load ID, pickup/delivery windows, rate, and carrier contact details.
   - Attach generated Rate Confirmation PDF.
   - Insert draft email into Outlook Draft Queue / Control Center.

### Human Review & Send Gate
- Publisher **may produce** packets, documents, and email drafts.
- Publisher **may NOT send** emails autonomously or commit financial terms.
- Mike Zachary reviews the draft in Outlook or Control Center and personally executes the send action.

---

## 3. TESTING APPROACH

`test_publisher.py` will verify:
- Publisher consumes committed `Mission Card` and correctly generates packet payload.
- Library templates and Archive examples are correctly retrieved and merged.
- Outlook draft email is generated with PDF attachment.
- Email is held in draft state requiring human approval before dispatch.

---

## 4. REQUIRED FINAL QUESTION: LOAD MOVEMENT SUMMARY

In the context of Publisher Worker:
- **Joe** captures dictation into an `OpportunityCard`.
- **Intelligence** scores dynamic capacity and recommends calendar slot.
- **Mike** commits the load on LOADS screen (State 1 Current Reality).
- **Publisher** consumes committed Mission Card, retrieves Library templates, produces rate confirmation packet, and generates Outlook email draft.
- **Mike** reviews draft in Outlook and clicks Send.
- **Dispatch** executes load (POP/POD uploads).
- **Archive** closes and stores load permanently.
