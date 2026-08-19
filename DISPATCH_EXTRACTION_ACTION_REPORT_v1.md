# DISPATCH EXTRACTION ACTION REPORT (v1)
**Operational Action Plan for SAM and Route Risk Extraction & Dispatch Freight Refactoring**

---

## SECTION 1: EXECUTIVE ACTION SUMMARY

### Target End-State Architecture
Dispatch is transitioning from a hybrid contract-opportunity and freight dispatcher into a dedicated **Freight Transportation Management System (TMS)** ready for its first real freight load test ("Run One Load").

* **Extracted Outside Dispatch**:
  1. **SAM (Government Opportunities Engine)**: Extracted into a standalone acquisition/intelligence service.
  2. **Route Risk Engine**: Extracted into a standalone external condition monitoring microservice.
* **Retained Inside Dispatch**:
  1. **Mission Visibility**: Tracking milestones (M1 through M10, including M6A Mid-Route Load Securement Check).
  2. **COMI (Communication & Operational Messaging Intelligence)**: Role-based messaging, data sanitization, Publisher drafts, and Operations Feed card generation.
  3. **Freight Core Execution**: Load booking, carrier dispatch, driver management, POD collection, financial settlement, and IFTA logging.

### Shortest Path Execution Sequence (Phase 1 to Phase 4)

```
[Current Hybrid State]
       │
       ├──► Phase 1: Detach SAM (Templates, Routes, Pipeline Helpers, Configs)
       │
       ├──► Phase 2: Detach Route Risk (Internal Engine, Feed Cards, Scoring Ties)
       │
       ├──► Phase 3: Refactor Dispatch Freight Core (UI Isolation, Navigation, Feed Aggregation)
       │
       └──► Phase 4: Run One Load Readiness Sequence (End-to-End Freight Test Verification)
```

1. **Phase 1: SAM Extraction**: Remove SAM UI routes (`portal/routes/pages.py`), template links (`base.html`, `sam.html`), helper functions (`load_and_process_sam`), environment variables (`DISPATCH_SAM_API_KEY`), and database integration registries without disrupting freight load acquisition (`cin_lite/acquisition.py`).
2. **Phase 2: Route Risk Extraction**: Isolate `dispatch/route_risk.py`, remove route risk card generators from `portal/models/operations_feed.py`, replace internal scoring ties in `dispatch/scoring.py` with external API contract stubs, and route external route risk alerts strictly through COMI triggers.
3. **Phase 3: Freight-Focused Isolation**: Clean up `portal/templates/home.html`, `brief.html`, and `settings.html` to display only active freight cards, driver portal assignments, and transportation management controls.
4. **Phase 4: Run One Load Verification**: Validate end-to-end freight lifecycle execution (Load Booking → Driver Dispatch → Milestone Tracking M1–M10 → M6A Securement Check → POD Closeout → Billing Export).

---

## SECTION 2: SAM EXTRACTION ACTION PLAN

### Target Files & Components Identified for Extraction
1. **Routes & Controllers**:
   * `portal/routes/pages.py`: Remove `@pages.route("/sam")` endpoint and SAM data fetching logic.
2. **Templates & Views**:
   * `portal/templates/sam.html`: Delete file / relocate to SAM service.
   * `portal/templates/base.html`: Remove SAM navigation tab (`<li><a href="{{ url_for('pages.sam') }}">SAM</a></li>`).
   * `portal/templates/home.html`: Remove SAM opportunity cards loop (`{% if sam_cards %}`) and total count summation.
   * `portal/templates/brief.html`: Remove SAM source link condition (`url_for('pages.sam')`).
   * `portal/templates/settings.html`: Remove SAM configuration parameters (`DISPATCH_SAM_LIMIT`, `DISPATCH_SAM_NAICS`, `DISPATCH_SAM_PTYPE`).
3. **Data Helpers & Processing**:
   * `portal/helpers.py`: Extract `load_and_process_sam()` function and its associated pipeline transformers.
   * `cin_lite/acquisition.py`: Remove `fetch_sam_opportunities()` and SAM API endpoint calls (`DISPATCH_SAM_API_KEY`).
4. **Registry & Configuration**:
   * `portal/models/integrations_registry.py`: Remove `DISPATCH_SAM_API_KEY` configuration entry.

### Step-by-Step SAM Extraction Action Sequence
1. **Step 2.1 (Config & Env Isolation)**: Unset `DISPATCH_SAM_API_KEY`, `DISPATCH_SAM_LIMIT`, `DISPATCH_SAM_NAICS`, and `DISPATCH_SAM_PTYPE` in `.env` and `portal/models/integrations_registry.py`.
2. **Step 2.2 (Backend Helper Detachment)**: Extract `load_and_process_sam()` from `portal/helpers.py` into the standalone SAM repository.
3. **Step 2.3 (Route Removal)**: Remove the `/sam` route definition from `portal/routes/pages.py`.
4. **Step 2.4 (Template Cleanup)**:
   * Remove the SAM tab link from `portal/templates/base.html`.
   * Update `portal/templates/home.html` to pass only `dispatch_cards` (Freight Loads) to the dashboard.
   * Remove `portal/templates/sam.html`.
5. **Step 2.5 (Pipeline Decoupling)**: Ensure `cin_lite/acquisition.py` handles freight contract acquisition exclusively.

---

## SECTION 3: ROUTE RISK EXTRACTION ACTION PLAN

### Target Files & Components Identified for Extraction
1. **Core Engine**:
   * `dispatch/route_risk.py`: Move file to standalone Route Risk Service repository. Replace inside Dispatch with a lightweight external webhook/API adapter.
2. **Scoring & Evaluation Modules**:
   * `dispatch/scoring.py`: Remove `compute_route_risk(load)` internal evaluation logic. Refactor load scoring to accept route risk parameters via external API payload input.
3. **Operations Feed Hooks**:
   * `portal/models/operations_feed.py`: Remove `_route_risk_cards()` internal generator and unhook `route_risk.list_route_risk_events()` call from feed aggregation.
4. **Services & Service Wrappers**:
   * `dispatch/services.py`: Refactor `record_route_risk_event()` and `get_route_risk()` wrappers to route to the external Route Risk API endpoint.
5. **UI & Driver Portal Views**:
   * `portal/templates/driver_home.html` & `portal/templates/brief.html`: Update route risk status rendering to ingest external Route Risk API JSON response via COMI.

### Step-by-Step Route Risk Extraction Action Sequence
1. **Step 3.1 (Engine Isolation)**: Move `dispatch/route_risk.py` logic to external service repository.
2. **Step 3.2 (Adapter Standard Creation)**: Create a standardized webhook receiver in `dispatch/services.py` (`receive_external_route_risk_event`) that accepts incoming HTTP POST alerts from the extracted Route Risk service.
3. **Step 3.3 (COMI Event Binding)**: Ensure incoming external route risk payloads automatically trigger `dispatch/comi_routing.py` (`evaluate_comi_routing`) with `trigger_type="route_risk_event"`.
4. **Step 3.4 (Feed Card Decoupling)**: Replace `_route_risk_cards()` in `portal/models/operations_feed.py` with an event-driven card reader that consumes evaluated COMI routing decisions rather than querying internal risk stores.
5. **Step 3.5 (Scoring Refactor)**: Modify `dispatch/scoring.py` so load scoring treats route risk as an external input attribute (`load.get("external_route_risk")`) rather than executing local environmental calculations.

---

## SECTION 4: DISPATCH FREIGHT CORE ISOLATION PLAN

### Refactoring Target List for Freight Isolation
1. **Dashboard Unification (`portal/templates/home.html`)**:
   * Re-theme home dashboard purely around Active Freight Movements, Pending Dispatches, Active Drivers, and Operations Feed Alerts.
   * Display real-time Freight Metrics: Active Loads, In-Transit Miles, Delivered PODs, and Unresolved Exceptions.
2. **Operations Feed Streamlining (`portal/models/operations_feed.py`)**:
   * Aggregate cards exclusively from active freight triggers:
     * Milestone Progress Cards (M1–M10, M6A).
     * COMI Exception & Publisher Draft Review Cards.
     * Driver Portal Check-in Notifications.
3. **Driver Portal & Milestone Enforcement**:
   * Ensure `portal/routes/driver_portal.py` enforces sequential milestone progression:
     * M1 (Dispatched) → M2 (En Route) → M3 (Arrived Origin) → M4 (Loading) → M5 (Loaded/BOL) → M6 (In Transit) → **M6A (Securement Check)** → M7 (Midway) → M8 (Arrived Consignee) → M9 (Unloading) → M10 (Delivered/POD).
4. **Accounting & Closeout Isolation (`dispatch/accounting_export.py`)**:
   * Ensure load closeout generates clean IFTA mileage logs, driver pay records, and QuickBooks freight invoices upon M10 completion.

---

## SECTION 5: RUN ONE LOAD READINESS SEQUENCE

Execution sequence required to perform Dispatch's first real freight load test ("Run One Load"):

```
[1. Load Booking & Rate Con] ──► [2. Driver Assignment] ──► [3. Origin Pickup (M1-M5)]
                                                                    │
[6. POD & Closeout (M10)]   ◄── [5. Consignee Delivery (M8-M9)] ◄── [4. In-Transit & M6A Check]
```

1. **Step 5.1 (Load Ingestion & Booking)**:
   * Create active freight load record (`LOAD-RUN-001`) with origin, destination, rate confirmation, equipment type (53ft Dry Van), and commodity details.
2. **Step 5.2 (Driver Assignment & PIN Generation)**:
   * Assign driver to `LOAD-RUN-001`. Generate authenticated driver portal access PIN via `portal/models/driver_pin_registry.py`.
3. **Step 5.3 (Origin Execution M1–M5)**:
   * Driver logs into Driver Portal, advances milestones M1 through M4, and uploads origin signed Bill of Lading (BOL) photo for M5.
4. **Step 5.4 (In-Transit & M6A Securement Check)**:
   * Driver operates along transit corridor (M6).
   * System executes M6A Mid-Route Load Securement Check after 150 miles / 3 hours continuous driving.
   * Driver submits cargo photo package and securement status via Driver Portal.
   * COMI evaluates M6A status (Green/Nominal) and generates internal Operations Feed card without external customer disclosure.
5. **Step 5.5 (Destination Delivery M8–M10)**:
   * Driver arrives at consignee (M8), starts unloading (M9), and uploads signed Proof of Delivery (POD) photo (M10).
6. **Step 5.6 (Closeout & Accounting Export)**:
   * Operations reviews POD in Operations Feed, approves load closeout, generates Publisher completion notice, and exports financial ledger entry to `reconciliation/` and `accounting_export.py`.

*Plan complete. Ready for execution upon authorization.*
