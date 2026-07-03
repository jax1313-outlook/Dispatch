# Hybrid — System Overview

**Hybrid (SDVOSB Contract Engine)** is a contract-locating, qualifying, and
pursuit-automation platform for a Service-Disabled Veteran-Owned Small Business.
It finds federal opportunities, screens them for **SDVOSB set-aside eligibility
and fit**, extracts deterministic intelligence, presents a human decision gate,
and — for pursued opportunities — assembles, signs, and submits an application
packet. It runs autonomously with a human in the loop.

## Design principles (invariants)
1. **Deterministic rules vs. non-deterministic agents are separated.** Rule
   modules and eligibility checks are deterministic and auditable; Claude agents
   (summarize / route / draft) are advisory helpers outside the rule path.
2. **Single Intelligence Owner.** Only the `HybridOrchestrator` (implementing the
   `IntelligenceOwner` contract) may produce unified intelligence. Operational
   nodes, controllers, and service workers must not.
3. **Human-in-the-loop control gate.** No pursuit/submission happens without a
   recorded human decision.
4. **Eligibility is first-class.** SDVOSB eligibility is a distinct layer, not a
   rule buried in scoring — it can hard-stop an opportunity.
5. **File-based, portable, auditable.** Every action is logged before it acts;
   artifacts are stored as structured files. No hidden state.
6. **Config over code.** Rules, routes, thresholds, and whitelists are JSON-driven
   and editable without code changes.

## Layered architecture
```
        ┌─────────────────────────────────────────────────────────────┐
        │                     Automation / Lifecycle                    │
        │        (orchestration, state machine, scheduling)             │
        └─────────────────────────────────────────────────────────────┘
  Intake ──▶ Eligibility ──▶ Intelligence ──▶ Decision ──▶ Generation ──▶ Execution
   (SAM,      (SDVOSB          (engines →       (human      (proposal      (sign +
    email)     set-aside,       score/rules/     checkbox     packet)        submit)
               VetCert,         routing)         gate)
               NAICS/size)
        └──────────────┬───────────────┬───────────────┬───────────────┘
                       ▼               ▼               ▼
                 Persistence: archive · audit log · reputation/knowledge base
                 Governance:  ownership guard · config · versioning
```

## Relationship to existing code (substrate)
Hybrid is the integration umbrella over work already built this session:

| Existing | Role in Hybrid |
|---|---|
| `cin-hybrid/` (CINRouter, engines, HybridIntelligence, HybridOrchestrator, HybridOps, services) | Core intelligence + operational engine |
| `cin_lite/` (SAM acquisition, 9 rule modules, Claude agents, checkbox email, archive) | Reference pipeline for Intake, Rules, Control, Archive |
| `D:/Email Helper` (rule engine + reputation) | Email-intake feeder + reputation model pattern |

## Open assumptions (pending confirmation)
These were asked but not yet answered; the architecture assumes the following and
flags them so they can be corrected:

- **A1 — Scope:** Hybrid is the *umbrella* integrating `cin-hybrid` + `cin_lite`
  patterns + Email-Helper intake (not a from-scratch rebuild).
- **A2 — Source of truth:** the code is authoritative going forward; the CIN-Lite
  `.docx` is historical context.
- **A3 — End-to-end spine:** acquire → eligibility → score/route → human approve →
  generate packet → sign → submit → track.
- **A4 — SDVOSB signals:** set-aside detection, VetCert/CVE status, NAICS + size
  standard, limitations on subcontracting, JV/MP structure. Data sources TBD.
- **A5 — Runtime:** local/file-based now; architecture leaves room for a later
  service tier but does not require it.

Correcting any assumption above updates `module_map.md`, the data-flow diagrams,
and the dependency map accordingly.

## Non-goals (current phase)
- No automated *bid decision without human approval*.
- No direct writes to government portals beyond the defined submission adapter.
- No storage of secrets in prompts, logs, or the knowledge base.

## Companion directories (owned outside this role)
`workflows/`, `data_model/`, `templates/`, `qa/` exist in the tree and are
referenced by these documents, but their contents are authored elsewhere.
