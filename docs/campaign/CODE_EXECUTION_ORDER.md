# CODE EXECUTION ORDER — DISPATCH / JOE CAMPAIGN
**Designation:** EXEC-ORDER v1.0
**Authority:** Mike Zachary, Owner/Operator, Level 1 Transport Inc.
**Date:** 2026-09-07
**To:** Claude Code (Staff Engineer role per JOE_CONVERSATIONAL_MISSION.md §1B)

---

## Read first, in this order

1. **JOE_CONVERSATIONAL_MISSION.md** — governing document. All doctrine, roles, classes, phases, prohibitions, and the validation register. Binding on every step below.
2. **CONOPS_v1.1.md** — ratified operating architecture (node + tablet, degraded modes, session model, glossary).
3. **OPPORTUNITY_CAPTURE_PLAN.md** — the seventh contract and the walking-skeleton workflow.
4. **CODE_MISSION_MCP_SERVER.md** — the MCP server + brain-neutral instructions mission.
5. **CLAUDE_HARNESS_ACTIVATION.md** — READ AND DO NOT BUILD. Sealed envelope; nothing in it is authorized.
6. **CONOPS_EVALUATION.md** — closed; context for why v1.1 says what it says.

Conflicts between documents: the governing document wins; report the conflict rather than resolving it silently. Anything ambiguous: Class 3 — staff work, recommendation, hold for Owner.

## Standing ground rules (all steps)

- Contract-First / Vendor-Agnostic Rule enforced by the neutrality scan; the scan must pass after every step.
- Doc/code equality: contracts in code must exactly match §8.1 (seven, including Opportunity Capture). A test asserts equality, not sufficiency.
- Code's operational classes (§1B) apply: destructive or history-bearing actions (deletes, force-pushes, rewrites, migrations) are Class 2 — state first, execute on Owner confirmation. Doctrine and contract changes are Class 3 — never yours.
- Honest Reporting Rule: no false success, no silent failure; partial results reported part by part, standard vocabulary (LIVE / CONFIGURED / UNVERIFIED, PASS / FAIL).
- ROGER control: remains UNVERIFIED, not implemented.
- No board automation, scraping, or session tooling of any kind, anywhere.

## Execution sequence — STOP at every ⛔ for Owner ruling

### Step 0 — Reconnaissance (report only) ⛔
Sweep D:\ for every folder you have ever written to: contract files, adapters, gateway_health.py, neutrality tests, msg*.txt commit files, stray .git directories. Produce a map — every location, contents, file dates, and every file existing in multiple places with differences noted. **Move, delete, and modify nothing.** Report and stop; the Owner rules on canonical locations.

### Step 1 — Consolidation (per Step 0 rulings) ⛔
- Establish the canonical repository per Owner ruling; copy winners in; connect the GitHub remote. Never force-push; divergent histories go to branches for Owner review.
- **Secret scan before any push** — tokens, credentials, .env; .gitignore runtime debris (logs/, __pycache__, proof/, caches).
- Plant at repo root: the six documents above, the governance package as located in Step 0, and a **CLAUDE.md** that (a) points to the governing document and doctrine, (b) states the locked vocabulary and the Class system, (c) instructs every session to read them before working.
- **Prove it:** a fresh session in the canonical folder must recite the doctrine essentials unprompted. Report and stop.

### Step 2 — Blocker verification
Owner tasks (not yours): set DISPATCH_JOE_TOKEN; install and register the On-Premises Data Gateway on the node. Your task: re-run `adapters/gateway_health.py` and the readiness report after the Owner reports done. Phase 1 readiness must show PASS/PASS before Step 4's live tests mean anything. If the Owner orders Steps 3–4 built before blockers clear, build — but readiness stays FAIL and says so.

### Step 3 — Seventh contract: Opportunity Capture
Build per OPPORTUNITY_CAPTURE_PLAN.md §§2–4: `POST /api/joe/opportunity`, Class 1 enforcement, sparse-capture validity, dedup logic with its own tests, audit entries, equality test updated to seven. Parser field order derives from the Mission Card form definition (single source of truth — never hardcode the sequence). Report.

### Step 4 — MCP server + instructions
Execute CODE_MISSION_MCP_SERVER.md in full (tools 1:1 with the seven ratified contracts; capture is the shakedown workflow). Run THE CAPTURE TEST end to end (plan §7), including the fail-closed path. Deliver AGENT_INSTRUCTIONS.md marked DRAFT for Owner ratification. Report with connection instructions for local clients. ⛔

### Step 5 — Node hardening (CONOPS v1.1, commissioned but sequenced last)
In order, each reported separately: (a) unattended recovery — services on boot, self-test reporting node status on recovery (BIOS auto-power-on and auto-login are Owner hands-on tasks; document the exact settings for him); (b) nightly encrypted off-node backup with the audit shipped more frequently — destination per Owner (home NAS), restore procedure documented and tested to a temp location; (c) portal session expiry and node-side revocation per the tablet trust boundary. No secrets on the tablet, ever.

## Out of scope of this order
Everything in CLAUDE_HARNESS_ACTIVATION.md · Track 2 Mission Screen UI (separate commissioning) · Phases 2–4 capabilities (templates, email send, sweep, Decision Engine) · any Copilot Studio configuration (Owner-side, Track 1).

## Final report
One campaign report against this order: each step's status in standard vocabulary, the validation register state, what exceeded or fell short, and the exact next actions that are the Owner's alone.
