# DISPATCH WORKER INTEGRATION PLAN
**Document ID:** 02_WORKER_INTEGRATION_PLAN.md
**Status:** BINDING INTEGRATION SPECIFICATION
**Location:** D:\Dispatch Operations\Workers\Governance\02_WORKER_INTEGRATION_PLAN.md
**Authority:** Mike Zachary / Dispatch Platform Doctrine

---

## 1. OVERVIEW & SCOPE

This document specifies the exact integration map for Joe, Intelligence, and Publisher workers inside the Authoritative Development Workspace `D:\Dispatch Operations\Workers\`.

Workers integrate inside existing Dispatch subsystems:
- `Joe`: Interfaces with `dispatch/opportunities.py` and `portal/models/identity.py`.
- `Intelligence`: Interfaces with `dispatch/capacity.py` and `dispatch/spine/`.
- `Publisher`: Interfaces with `portal/models/publisher.py`, `portal/models/library.py`, and `dispatch/connectors/outlook_connector.py`.
