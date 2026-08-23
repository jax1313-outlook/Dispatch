# DRIVER PORTAL ARCHITECTURE V2

**Document Type:** Architecture & Interface Specification
**Program:** Dispatch / Driver Portal
**Authority:** Mike Zachary remains final authority.
**Governing Doctrine:** `DRIVER_FIRST_DOCTRINE_v2`
**Core Test:** The 70 MPH Test (D2)

---

## 1. Executive Summary

The Driver Portal operates under the governing **Driver-First Doctrine** and the **70 MPH Test**.
It is strictly an **execution interface**, NOT an opportunity management workspace, dispatch planner, or scheduling board.

Purpose:
> **Mission Execution**

---

## 2. Cockpit Architecture

The Driver Portal UI is organized into a **Week View + Current Mission** dual-layer cockpit model:

```
┌─────────────────────────────────────────────────────────────┐
│                     DRIVER PORTAL V2                        │
├─────────────────────────────────────────────────────────────┤
│  LAYER 1: CURRENT MISSION (Priority #1)                     │
│  • Current Load ID / Customer / Route                       │
│  • Pickup & Delivery Appointments                           │
│  • Live Status Stepper & Milestone Actions                  │
│  • Navigation / Map Direct Link                             │
│  • Emergency Contacts (Dispatch / Broker)                   │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: WEEK VIEW (Capacity Visualization)                │
│  • Available Capacity Days / Windows                        │
│  • Consumed Capacity (Committed Loads)                      │
│  • Position Traps / Schedule Gaps                           │
├─────────────────────────────────────────────────────────────┤
│  SUPPORTING EXECUTION MODULES                               │
│  • Milestones (Driver Status Updates)                       │
│  • POD (Proof of Delivery / Document Capture)               │
│  • Contacts (Dispatch Email & Broker Contact Lookup)        │
│  • Fuel (IFTA Fuel Purchase Entry & Receipt Upload)         │
│  • Settlement (Driver Pay & Invoice Status Review)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Scope Boundaries & Prohibitions

### What Driver Portal IS:
- Current Mission Execution
- Week View Capacity Awareness
- Contact Retrieval
- Turn-by-Turn / Navigation Linkage
- Milestone Reporting
- POD / Document Upload
- Fuel Receipt Capture
- Settlement & Pay Transparency

### What Driver Portal IS NOT:
- **NOT** an opportunity management workspace
- **NOT** a dispatch load board / candidate evaluation tool
- **NOT** a dispatch planner or scheduling system
- **NOT** an automated decision agent

---

## 4. Key Operational Capabilities & Doctrine Mapping

1. **Current Mission Priority (D1, D2, D3):**
   - The driver sees active load info, next expected milestone, and immediate contact info within 2 seconds.
   - High contrast, single-tap actions for status updates (e.g., Arrived Pickup, Loaded, Arrived Delivery, POD Uploaded).

2. **Operational Retrieval & Safety (D6, D9):**
   - Lookup paths in the Driver Portal use plain operational language (Load #, Customer, Location).
   - Lookup paths are strictly read-only and cannot accidentally alter load records, financial terms, or dispatch status.

3. **External Disclosure Compliance (D11):**
   - Internal company P&L, expenses, profit margins, and internal dispatch notes are **never** displayed to drivers or external parties via the portal.
   - Driver pay and settlement displays show driver earnings, rate type, and payment status cleanly without disclosing company margin.

4. **Load-Ownership & Security Verification:**
   - Every API endpoint or page route accepting a load ID enforces strict driver ownership verification (`driver_id` matching active session) to eliminate Insecure Direct Object Reference (IDOR) vulnerabilities.
