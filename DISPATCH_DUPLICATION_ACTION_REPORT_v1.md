# DISPATCH DUPLICATION ACTION REPORT (v1)
**Independent Ownership & Dependency Duplication Plan for SAM and Route Risk Extraction**

---

## SECTION 1: DOCTRINAL GOVERNANCE — THE MIKE RULE

```
================================================================================
                               THE MIKE RULE
================================================================================
 If a shared dependency is:
   1. Working
   2. Stable
   3. Small
   4. Easier to duplicate than redesign

 THEN:
   CLONE IT.

   - Dispatch keeps the original file.
   - SAM receives an independent copy.
   - Route Risk receives an independent copy where required.

 RULE OF THUMB:
 Independent Ownership is strictly preferred over Shared Dependencies.
 NO shared infrastructure.
 NO central service buses.
 NO common utility repositories or SDK packages.
================================================================================
```

---

## SECTION 2: SYSTEMATIC ANALYSIS OF THE EIGHT EXTRACTION LANDMINES

This section analyzes the eight extraction landmines identified during architecture review and applies **THE MIKE RULE** to establish independent file ownership before extraction begins.

### Landmine 1: `email_delivery.py` / Email Helper Modules
* **Current State**: `portal/models/email_helper.py` and `dispatch/customer_notifications.py` serve both SAM email alerts and Dispatch freight notifications.
* **Extraction Hazard**: Modifying email templates or delivery configurations for SAM risks breaking freight load confirmation and driver dispatch emails.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/models/email_helper.py` and `dispatch/customer_notifications.py` (Originals).
  * **SAM**: Clones `sam_email_helper.py` into SAM repository, pre-configured with government opportunity notification parameters.
  * **Route Risk**: Clones `rr_email_helper.py` into Route Risk repository for external weather/traffic emergency alerts.

### Landmine 2: `_trigger_govcon_draft()` & Draft Pipeline Helpers
* **Current State**: `cin_lite/control.py` and `portal/models/publisher.py` contain `_trigger_govcon_draft()` helper logic mixed alongside freight load publisher actions.
* **Extraction Hazard**: Deleting govcon draft generators inside Publisher risks breaking freight exception draft generation for customers/brokers.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/models/publisher.py` (Original), stripped of `_trigger_govcon_draft()` calls, dedicated to freight exceptions and COMI updates.
  * **SAM**: Clones `sam_publisher.py` and `sam_control.py` into SAM repository, retaining full `_trigger_govcon_draft()` logic.
  * **Route Risk**: Not required (Route Risk triggers Publisher Drafts via Dispatch's external COMI webhook API).

### Landmine 3: Shared Sandbox (`portal/models/sandbox.py`)
* **Current State**: `sandbox.py` stores both SAM contract opportunities and Dispatch freight loads in a single local JSON store (`sandbox.json`).
* **Extraction Hazard**: Data contamination, key collision, or file locking issues when extracting SAM.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/models/sandbox.py` (Original), restricted strictly to `source_type="dispatch"` freight loads.
  * **SAM**: Clones `sam_sandbox.py` into SAM repository with a dedicated `sam_sandbox.json` store.
  * **Route Risk**: Clones `rr_store.py` into Route Risk repository with a dedicated `rr_events.json` store.

### Landmine 4: Shared Archive (`portal/models/archive.py` & `cin_lite/archive.py`)
* **Current State**: `archive.py` handles retention archiving for both SAM contracts and Dispatch freight completion packets.
* **Extraction Hazard**: Modifying the archive schema or folder directory tree (`DISPATCH_ARCHIVE_ROOT`) risks corrupting historical freight PODs and IFTA records.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/models/archive.py` (Original), dedicated strictly to freight POD packages, signed BOLs, and IFTA trip leg logs.
  * **SAM**: Clones `sam_archive.py` into SAM repository, maintaining government contract metadata bundles.
  * **Route Risk**: Clones `rr_archive.py` into Route Risk repository for logging environmental and corridor risk event history.

### Landmine 5: Shared Authentication & Route Exemptions (`portal/app.py`)
* **Current State**: `portal/app.py` enforces global session auth while maintaining exemption lists for SAM callbacks, driver portal access, and stakeholder portal HMAC tokens.
* **Extraction Hazard**: Refactoring auth rules risks locking out driver portal sessions or exposing internal dispatch routes.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/app.py` (Original) with auth exemptions restricted to Driver Portal (`/driver`), Stakeholder Portal (`/stakeholder`), and COMI Webhooks (`/api/comi`).
  * **SAM**: Clones `sam_app.py` into SAM repository with auth rules specific to government opportunity decision endpoints.
  * **Route Risk**: Clones `rr_app.py` into Route Risk repository with lightweight API key authentication for external alert posting.

### Landmine 6: Shared UI Templates (`base.html`, `home.html`, `brief.html`, `settings.html`)
* **Current State**: Jinja templates contain conditional logic rendering SAM opportunities and Dispatch freight cards side-by-side.
* **Extraction Hazard**: Deleting Jinja tags risks breaking CSS layouts or JavaScript card interaction handlers on the main dispatch dashboard.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains and cleans original templates (`base.html`, `home.html`, `brief.html`, `settings.html`), removing SAM conditionals to present a clean Freight TMS interface.
  * **SAM**: Clones template package into SAM repository (`sam_base.html`, `sam_home.html`, `sam_brief.html`, `sam_settings.html`), optimized for government contract opportunity review.
  * **Route Risk**: Independent standalone dashboard templates (`rr_dashboard.html`).

### Landmine 7: Shared Configurations (`integrations_registry.py` & `cin_config`)
* **Current State**: Environment variables (`DISPATCH_SAM_API_KEY`, `PORTAL_SECRET_KEY`) and `integrations_registry.py` manage credentials for all modules together.
* **Extraction Hazard**: Removing SAM keys risks invalidating registry lookup functions or breaking environment loading.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `portal/models/integrations_registry.py` (Original), purging SAM variables and retaining freight integration keys (Motive, Samsara, QuickBooks Online).
  * **SAM**: Clones `sam_integrations_registry.py` into SAM repository, retaining `DISPATCH_SAM_API_KEY` and SAM API query limit settings.
  * **Route Risk**: Clones `rr_config.py` into Route Risk repository for managing NOAA, DOT, and Weather feed API credentials.

### Landmine 8: Shared Notification Helpers (`dispatch/notifications.py`)
* **Current State**: `dispatch/notifications.py` handles HMAC token generation, link signing, and email dispatch for both contract decision links and freight updates.
* **Extraction Hazard**: Changing HMAC token signatures for SAM email links risks invalidating active driver portal access tokens or stakeholder decision links.
* **Duplication Action under The Mike Rule**:
  * **Dispatch**: Retains `dispatch/notifications.py` (Original), dedicated to driver PIN verification and COMI stakeholder decision links.
  * **SAM**: Clones `sam_notifications.py` into SAM repository with independent HMAC secret signing (`SAM_EMAIL_SECRET`).
  * **Route Risk**: Clones `rr_notifications.py` into Route Risk repository for emergency push notifications.

---

## SECTION 3: COMPLETE DEPENDENCY DUPLICATION MATRIX

This matrix identifies every target dependency and defines its explicit cloned destination before extraction begins.

| Shared Dependency Component | Dispatch (Original Retained) | SAM (Cloned Destination) | Route Risk (Cloned Destination) |
|---|---|---|---|
| **Email Helper** | `portal/models/email_helper.py` | `sam_email_helper.py` | `rr_email_helper.py` |
| **GovCon Draft Generator** | N/A (Removed from Dispatch) | `sam_control.py` | N/A |
| **Sandbox Store** | `portal/models/sandbox.py` (`sandbox.json`) | `sam_sandbox.py` (`sam_sandbox.json`) | `rr_store.py` (`rr_events.json`) |
| **Archive Model** | `portal/models/archive.py` | `sam_archive.py` | `rr_archive.py` |
| **Auth & App Core** | `portal/app.py` | `sam_app.py` | `rr_app.py` |
| **UI Templates** | `portal/templates/` (Freight Cleaned) | `sam_templates/` | `rr_templates/` |
| **Integrations Registry** | `portal/models/integrations_registry.py` | `sam_integrations_registry.py` | `rr_config.py` |
| **Notification Signer** | `dispatch/notifications.py` | `sam_notifications.py` | `rr_notifications.py` |

---

## SECTION 4: DOCTRINAL GUARANTEE

```
================================================================================
                          INDEPENDENCE GUARANTEE
================================================================================
 Under this Duplication Action Plan:
   1. NO shared Python packages or common utility libraries are created.
   2. NO shared databases or multi-tenant stores remain.
   3. NO inter-service message buses (RabbitMQ, Kafka, Redis PubSub) are introduced.
   4. Dispatch, SAM, and Route Risk operate as 100% self-contained units.

 Communication between extracted systems occurs strictly via documented HTTP webhooks
 routed through Dispatch's COMI interface.
================================================================================
```

*Mike decides. Dispatch executes.*
