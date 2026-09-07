# CODE MISSION — DISPATCH MCP SERVER + BRAIN-NEUTRAL INSTRUCTIONS
**Designation:** CODE-MCP v1.0
**Authority:** Mike Zachary, Owner/Operator, Level 1 Transport Inc.
**Date:** 2026-09-06
**Governing document:** JOE_CONVERSATIONAL_MISSION.md (read it first; all doctrine applies)

---

## Intent

Build the swap-ready pieces of the brain-independence posture, per Owner ruling: contracts + MCP server + instructions document are built now and kept battle-ready by daily use; the Claude harness is NOT built (see CLAUDE_HARNESS_ACTIVATION.md — do not implement anything listed there).

## Deliverable 1 — Dispatch MCP Server

An MCP (Model Context Protocol) server exposing the six ratified Dispatch contracts as MCP tools, for use by local AI clients (Claude Code, Claude Desktop) today and any MCP-capable brain later.

**Requirements:**
1. **Placement:** `adapters/mcp/`. The server is an adapter in role. The authoritative contract layer is not modified in any way by this mission.
2. **Architecture rule — client of the API, never a bypass:** the MCP server calls the Dispatch HTTP API over localhost. It must not import Spine internals or touch the database directly. Every doctrine control enforced at the API (authentication, authority classes, fail-closed 503, audit logging) therefore remains in force underneath it. If the API is down or the token unset, the MCP server reports that honestly — it does not work around it.
3. **Tools:** exactly six, mapping 1:1 to the six endpoints in JOE_CONVERSATIONAL_MISSION.md §8.1. A test asserts equality with the contract, not sufficiency (same pattern as the endpoint-count test).
4. **Authority classes carried through:** the two Class 2 tools (mission-record correction, send-notice) require an explicit `confirmed` parameter, defaulting false, and their tool descriptions must state the read-back requirement so any consuming brain is instructed at the protocol level.
5. **Transport:** stdio (client-launched, on-demand, zero standing cost — laptop-appropriate). No network listener in this mission. Provide the config snippet for connecting Claude Code and Claude Desktop, in the final report.
6. **Language/SDK:** Python, official MCP SDK.
7. **Identity:** every call carries driver identity through to the API per the attribution rule; the server adds a `via: MCP` channel marker using nature-naming (never a product name) so the audit log records the door used.
8. **Tests:** tool/contract parity; Class 2 confirmation enforcement; honest failure when API unreachable or token unset. Run the full existing suite plus the neutrality scan and report results — the scan must still pass untouched.

## Deliverable 2 — AGENT_INSTRUCTIONS.md (brain-neutral)

The doctrine of JOE_CONVERSATIONAL_MISSION.md §1A, §2, §3 translated into a provisioning document any brain can be loaded with: role definition, declarative voice rule and locked vocabulary, the three operational classes with their confirmation behavior, honest reporting rule, prohibitions. No vendor names anywhere in it. Derive strictly from the governing document — invent nothing. Mark it DRAFT pending Owner ratification.

## Explicitly out of scope
- Any part of the Claude harness (agent loop, phone channel, email/calendar adapters, billing) — reserved to CLAUDE_HARNESS_ACTIVATION.md.
- Network exposure of the MCP server (tunnel/gateway wiring) — later mission.
- Any change to contracts, endpoints, or authority classes.
- Any read or write of operational records beyond what tests require against test fixtures.

## Report (standard vocabulary)
1. Build report: what was created, where, test results.
2. Connection instructions for Claude Code and Claude Desktop (the config snippet, and the one-line usage note for the Owner).
3. Status line for the register: MCP SERVER: LIVE / CONFIGURED / UNVERIFIED, with reasons.
4. Anything exceeding or falling short of this mission, stated plainly. No false success, no silent failure.
