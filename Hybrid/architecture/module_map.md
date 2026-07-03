# Hybrid — Module Map

Modules grouped by layer. Each lists its **responsibility**, **inputs**,
**outputs**, and the **existing code** that realizes it (or `NEW` if not yet
built). Contracts named here are defined in `integration_points.md`.

## Intake Layer
### `acquisition`
- **Responsibility:** Pull federal opportunities from designated sources.
- **Inputs:** source config (SAM.gov API key, filters, NAICS, date window).
- **Outputs:** raw opportunity records (normalized dicts).
- **Realized by:** `cin_lite/acquisition.py` (SAM.gov) + `cin-hybrid` SAM engine.

### `email_intake`
- **Responsibility:** Capture inbound email (RFP notices, teaming, correspondence)
  as normalized items; triage/route.
- **Inputs:** `.eml`/`.txt` from an Intake folder (Outlook rule / manual export).
- **Outputs:** parsed messages (sender, subject, body, links) + routing/reputation.
- **Realized by:** `D:/Email Helper` (parser, rules, reputation).

### `vendor_profile`
- **Responsibility:** Load & normalize the SDVOSB's own capability profile
  (NAICS, certifications, past performance, cyber posture, contacts).
- **Inputs:** vendor id → profile source (JSON now; SAM/DB later).
- **Outputs:** `vendor_profile` dict.
- **Realized by:** `cin-hybrid` `JSONVendorLoader` (`load_vendor`).

## Eligibility Layer
### `set_aside_eligibility` — **NEW**
- **Responsibility:** Determine whether the SDVOSB can compete on an opportunity.
- **Inputs:** opportunity (set-aside type, NAICS, agency) + `vendor_profile`.
- **Outputs:** `eligibility_verdict` {eligible: bool, basis, blockers[], signals}.
- **Checks:** set-aside detection, VetCert/CVE status, NAICS + size-standard fit,
  limitations on subcontracting, JV/MP structure.
- **Realized by:** partly `cin_lite` rule modules (set-aside, NAICS, subcontractor,
  JV/MP); **VetCert/size-standard verification is NEW.**

## Intelligence Layer
### `engines`
- **Responsibility:** Deterministic per-domain analysis (gov, vendor network,
  cyber compliance, pricing, foreign influence, past performance, …).
- **Inputs:** opportunity + `vendor_profile` via `CINRouter.dispatch`.
- **Outputs:** per-engine findings dicts.
- **Realized by:** `cin-hybrid/core/agents/*_engine.py` + `cin_lite/rules/*`.

### `hybrid_intelligence` (the Intelligence Owner)
- **Responsibility:** Aggregate engine output → summary → scoring → rule flags →
  CIN routing → unified intelligence product.
- **Inputs:** engine findings (+ eligibility_verdict).
- **Outputs:** `intelligence` {summary, scoring, rules, routing, intel_version}.
- **Realized by:** `cin-hybrid` `HybridSummary` → `HybridIntelligence`
  (`CINScoringModel`, `RuleModules`, `CINRouting`) → `HybridOrchestrator`
  (`IntelligenceOwner`), guarded by `intelligence_guard`.

## Decision Layer
### `control`
- **Responsibility:** Present a human decision gate (checkbox email) mapping a
  choice to a route; record it.
- **Inputs:** `intelligence` + summary.
- **Outputs:** recorded human `action` → route (approve-proposal/archive/reject/
  flag/deeper-analysis).
- **Realized by:** `cin_lite/control.py` + `email_delivery.py`.

## Generation Layer
### `proposal_packet`
- **Responsibility:** Assemble the application/proposal packet (brief, forms,
  attachments, outline).
- **Inputs:** opportunity + `vendor_profile` + `intelligence`.
- **Outputs:** `packet` {forms, attachments, pdf_path, status}.
- **Realized by:** `cin_lite` proposal workflow + `cin-hybrid` packet builder.

## Execution Layer
### `signature`
- **Responsibility:** Route the packet through external sign/edit and retrieve the
  signed artifact.
- **Inputs:** `packet` (pdf_path), signer identity.
- **Outputs:** signed `packet` (updated pdf_path, status).
- **Realized by:** `cin-hybrid` `DocuSignBridge`.

### `submission`
- **Responsibility:** Deliver the final packet to the target (email/portal).
- **Inputs:** signed `packet`, recipient.
- **Outputs:** submission receipt + status.
- **Realized by:** `cin-hybrid` `OutlookEmailClient` (`send_packet`); portal adapter NEW.

## State & Governance
### `lifecycle`
- **Responsibility:** Track opportunity/packet state; orchestrate step order.
- **Inputs:** events from each layer.
- **Outputs:** state transitions (loaded → … → submitted).
- **Realized by:** `cin-hybrid` `HybridLifecycleController` + `HybridOps`.

### `archive` / `audit_log`
- **Responsibility:** Persist raw/processed/intelligence/routing/proposals; log
  every action before it acts; keep reputation/knowledge base.
- **Realized by:** `cin_lite/archive.py`, `logger`, Email-Helper reputation.

### `ownership_guard` / `config`
- **Responsibility:** Enforce the single-Intelligence-Owner invariant; load
  JSON config (rules, routes, thresholds, whitelist, settings).
- **Realized by:** `cin-hybrid` `intelligence_guard` / `intelligence_api`; JSON config.

## Companion (not authored here)
`workflows/` (step definitions), `data_model/` (schemas), `templates/` (packet &
email templates), `qa/` (tests, evals) — referenced by build sequence and flows.
