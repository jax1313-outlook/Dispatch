# Hybrid — Integration Points

## External integrations
| # | System | Direction | Data exchanged | Auth | Failure / fallback |
|---|--------|-----------|----------------|------|--------------------|
| E1 | SAM.gov Opportunities API | in | opportunity records | api.data.gov key | HTTP error → fall back to local sample data; log |
| E2 | VetCert / CVE (SDVOSB status) — **NEW** | in | veteran-owned verification status | TBD | unknown status → eligibility "unverified" (soft block) |
| E3 | SBA size standards / NAICS table — **NEW** | in | size threshold per NAICS | static file or API | missing → flag "size unverified" |
| E4 | Claude API (agents) | out/in | summary / routing / draft requests | `ANTHROPIC_API_KEY` | unavailable → deterministic fallback |
| E5 | Microsoft Graph / Outlook | in & out | email intake; packet submission | OAuth (Graph) | send failure → retry/queue; log |
| E6 | DocuSign REST | out/in | envelope create / status / signed PDF | bearer token | poll timeout → lifecycle "sign_stalled" |
| E7 | SMTP (control emails) | out | checkbox decision emails | SMTP creds | unconfigured → write `.eml` to Outbox |
| E8 | Filesystem archive | out | raw/processed/intel/routing/proposals | OS perms | folder missing → create; never delete pre-log |

## Internal contracts (module-to-module)
These are the stable seams; changing them is a versioned event (see
`versioning_strategy.md`).

| # | Contract | Producer → Consumer | Shape |
|---|----------|---------------------|-------|
| I1 | `run_intelligence(vendor_id) -> dict` | `HybridOrchestrator` (IntelligenceOwner) → callers via `intelligence_api.get_intelligence` (guarded) | {summary, scoring, rules, routing, intel_version} |
| I2 | `CINRouter.dispatch(engine, action, payload)` | orchestration → engines | engine exposes `action(payload)` method |
| I3 | `eligibility_verdict` | `set_aside_eligibility` → intelligence + control | {eligible, basis, blockers[], signals} |
| I4 | control `action` → route | `control` → lifecycle/archive | one of five actions → route + recorded decision |
| I5 | `vendor_profile` | `vendor_profile.load_vendor(id)` → engines/packet | normalized profile dict |
| I6 | `packet` | `proposal_packet.build` → signature → submission | {forms, attachments, pdf_path, status, version} |
| I7 | service client contracts | services → `HybridOps` | `load_vendor`, `send_packet`, `packet_builder.build`, DocuSign `send/wait/retrieve` |
| I8 | config | `config` (JSON) → all layers | rules / routes / thresholds / whitelist / settings |

## Governance seams
- **G1 — Ownership guard:** `enforce_intelligence_owner(obj)` raises unless `obj`
  is an `IntelligenceOwner`. All intelligence access flows through
  `intelligence_api.get_intelligence`.
- **G2 — Human gate:** no transition into Generation/Execution without a recorded
  `control` decision (I4).
- **G3 — Eligibility gate:** a hard `eligibility_verdict.eligible == false` blocks
  pursuit regardless of score.

## Notes
- Every external integration has a **degraded-mode fallback** so the pipeline is
  never hard-blocked by an outage (principle 5, `system_overview.md`).
- New adapters (E2/E3, portal submission) must publish a contract here before build.
