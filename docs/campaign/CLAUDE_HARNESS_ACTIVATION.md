# CLAUDE HARNESS ACTIVATION PLAN
**Designation:** WAR-RESERVE v1.0
**Authority:** Mike Zachary, Owner/Operator, Level 1 Transport Inc.
**Date:** 2026-09-06
**Status:** SHELVED BY DESIGN — build nothing in this document until activation is ordered.

---

## Purpose

This document is the sealed envelope. It records what must be built *around a Claude brain* for it to serve as Joe, so that a future activation is a short, known mission instead of a research project. Per Owner ruling: the swap option is maintained as contracts + MCP server + instructions document, kept battle-ready by daily use and acceptance tests; the harness is built on the day it is needed, not before.

## Activation triggers (any one, Owner decides)
- Copilot fails an acceptance test that matters (Email Test, read-back fidelity, declarative voice) and cannot be corrected.
- Copilot pricing, licensing, or capability changes break the Rent-the-Trailer economics.
- Product discontinuation or a forced platform change.
- Owner ruling for any other reason. (Class 3 decision — always human.)

## Already on hand at activation (do not rebuild)
- The six vendor-agnostic contracts with authority classes and append-only audit — in daily service.
- The Dispatch MCP server (`adapters/mcp/`) — in daily service with local Claude clients; any MCP-capable brain couples to it.
- AGENT_INSTRUCTIONS.md — brain-neutral doctrine, ratified, current.
- The acceptance tests (JOE_CONVERSATIONAL_MISSION.md §9) — the certification bar, brain-blind by design.
- The audit log, token auth, and fail-closed posture beneath everything.

## Must be built at activation

1. **Agent harness.** The loop that runs Claude with AGENT_INSTRUCTIONS.md as its provisioning, connected to Dispatch through the MCP server. Expected tooling: Anthropic Agent SDK (verify current name/state at activation — this is the part that churns, which is why it is not pre-built). Runs on the Dispatch node.
2. **Driver channel.** How Mike talks to Claude-Joe from the road. Options at time of writing, verify at activation: the Mission Screen's Joe panel pointed at the harness instead of the rented brain (Track 2 makes this nearly free); a minimal chat endpoint in the Driver Portal; voice layer later, 70 MPH Test applies. Note: the Teams channel does not follow the swap — it belongs to the old brain's platform.
3. **Email/calendar adapters.** The largest single item. Copilot's native M365 connectors are replaced by adapters (Microsoft Graph API) for: read/summarize/draft/revise/send email; read/create/revise/remove calendar entries. Contract-first: define email/calendar capability contracts, then the Graph adapter — vendor name in the adapter only. The Email Test (§9) is the acceptance bar.
4. **Identity mapping.** Driver identity to API attribution, replacing platform-native identity. Small but doctrine-critical: audit attribution must survive the swap unchanged.
5. **Cost switch.** Per-token API billing replaces flat subscription. At activation: estimate monthly volume from the audit log (real usage data will exist by then), set a billing alert, record the number in this document.
6. **Certification.** Run the full §9 acceptance suite against Claude-Joe. No cutover on anything less than full PASS, including the honest-failure paths.
7. **Cutover and rollback.** Point the driver channel at the new harness; keep the old brain's configuration intact and dormant for 30 days as rollback; retire it by Owner ruling only.

## Estimated activation effort
On the order of days, not weeks — items 1, 2, 4 are short given what's on hand; item 3 carries most of the weight. Estimate is unreliable until refreshed at activation against then-current SDKs.

## War reserve check (keeps the envelope honest)
Annually, or after any major contract change: a one-day mission — stand up a minimal harness, run the acceptance suite read-only tools only, record PASS/FAIL and the effort actually required, update this document, tear down. Pocket-change cost; converts this plan from belief to verified readiness. Schedule by Owner ruling.

## Standing cost of this posture
Zero while shelved. API billing is per-use; a capability that isn't running costs nothing to keep.
