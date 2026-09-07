# OPPORTUNITY CAPTURE — END-TO-END BUILD PLAN
**Designation:** OPP-CAPTURE v1.0
**Authority:** Mike Zachary, Owner/Operator, Level 1 Transport Inc.
**Ruled:** 2026-09-06 (seventh contract, JOE_CONVERSATIONAL_MISSION.md §8.1)
**Role in campaign:** Walking skeleton — the first real freight through the full stack. Certifies token auth, contract layer, audit log, doc/code equality discipline, and the MCP server with one live workflow. Also the Decision Engine's calibration data source: weeks of real niche freight before Phase 4 builds.

---

## 1. What it is

Owner reads a board listing (human eye, interactive session — within board terms). Owner dictates or types the capture. Joe logs it as an Opportunity in the Spine and answers "LOGGED." Scoring happens later (manually at first, by Decision Engine in Phase 4). No board automation exists anywhere in this workflow.

**Class 1** — internal, reversible, touches no Mission Record and no outside party. No read-back. Speed is the point: capture in seconds, move to the next listing.

## 2. The contract — `POST /api/joe/opportunity`

Vendor-agnostic per the Contract-First Rule. Fields:
- `source_board` (string, nature-named as the Owner says it — stored as given, never an enum of vendor products in the contract)
- `origin`, `destination` (city/state minimum)
- `rate` (number), `pieces/weight` (freeform ok), `equipment` (freeform ok)
- `pickup_date`, `delivery_date` (optional)
- `contact` (optional freeform — broker name/phone as dictated)
- `notes` (optional freeform)
- `captured_via` (channel, nature-named: VOICE, CHAT, MISSIONSCREEN, SWEEP)
- Server adds: `opportunity_id`, `captured_at`, `captured_by` (driver identity), audit entry.

Sparse capture is valid capture: only board, origin, destination, and rate are required. A capture with gaps beats a listing lost to the next screen.

## 3. Deduplication rule (concurrency doctrine — capture and sweep coexist)

Voice capture and the automated sweep (Phase 4) run simultaneously by design, into the same store. One load = one Opportunity record:
- Candidate match: same board + same origin/destination + rate within tolerance + overlapping pickup date.
- On match: merge into the existing record; append the new origin to the audit trail (e.g. captured VOICE 09:14, seen SWEEP 09:30). Sweep data enriches sparse voice captures (fills gaps), never overwrites Owner-dictated values.
- No match: new record. Ambiguous: new record flagged POSSIBLE DUPLICATE for the recommendation card to surface — the engine never silently guesses two loads are one.

## 4. Build steps (Code) — rides the existing queue, interrupts nothing

Sequence unchanged: recon sweep → consolidation → Owner sets token / installs gateway → then:

1. **Contract + endpoint + tests** — `POST /api/joe/opportunity`, Class 1 enforcement, audit entries, dedup logic with its own tests, equality test updated to seven. (Hours.)
2. **MCP tool** — added in the CODE_MISSION_MCP_SERVER.md build (already amended to track ratified contracts); capture becomes the MCP server's shakedown workflow.
3. **Connector action** — added to the Copilot custom connector definition alongside the other tools (Owner wires it in Copilot Studio during Track 1 setup).
4. **Storage** — Opportunity store in the Spine per Single Source of Truth; append-only audit as everywhere else.

## 5. Activation stages (each usable the day it lands)

- **Stage A — Desk capture (no gateway needed):** Claude Desktop/Code on the node, via MCP over localhost. First live end-to-end write: THE CAPTURE TEST below. Certifies the node stack.
- **Stage B — Cab capture (with Track 1):** Joe in Teams, gateway live. "Joe, log this one..." from the truck. Certifies the bridge. From this point capture runs at the boards' pace, wherever the Owner is.
- **Stage C — Sweep joins (Phase 4):** authorized board APIs feed the same store; dedup rule governs; engine scores both streams identically. Voice capture continues forever as the manual override and the TruckSmarter path (no carrier API found there yet).

## 6. Dictation protocol (the capture call)

**Canonical order = the blank Mission Card form, read top to bottom** (Owner ruling 2026-09-06). The Owner dictates by reading down the form he already knows; the form definition in Dispatch is the single source of truth for field order, and Code derives the parser's expected sequence from it — the protocol follows the form automatically if the form ever changes. This also makes capture and Mission Record the same shape from birth: graduation on "book it" is a promotion, not a field mapping.

Illustrative call (actual order per the form):

> "Joe, log this one: [board]. [Origin] to [destination]. [Pieces, weight, equipment]. $[rate]. Pickup [date/time], deliver [date/time]. Broker [company, name, phone]. Notes: [anything]."

Rules:
- **Required by voice: board, lane, rate.** Everything after money is optional — sparse capture is valid capture.
- **Joe asks at most one question, and only for the rate.** Missing rate → "RATE?" — Owner answers or says "skip"; Joe logs either way. Never more than one question per capture; speed outranks completeness.
- **Echo confirms the card:** "LOGGED. OPPORTUNITY [id]. [board], [lane], $[rate], [pickup]." Corrections are Class 1 and instant: "Correct rate to $850."
- Parsing is tolerant of natural speech (order deviations, filler); the canonical order is the fast path, not a straitjacket.

## 6A. Card lifecycle (how a capture travels the system — this begins the queue)

1. **Capture → Opportunity card.** Rendered recommendation-first per the v1.2 card ruling; missing fields flagged visibly on the card, never hidden.
2. **Queue.** The card sits in the Opportunity queue; the Decision Engine scores it (Phase 4; Owner's eye until then). Sweep-discovered data may enrich it per the dedup rule.
3. **Decision.** "Book it" is Class 3 — always the Owner. "Pass" archives the card (data retained for engine calibration).
4. **Graduation.** On "book it," the Spine creates the Mission Record from the card's data — no retyping — and Phase 2 workflows fire the acceptance email on the company template (Broker Call Test flow). The Opportunity card links to its Mission Record in the audit trail.

One dictated capture at the boards becomes, untouched by keyboard, the mission the truck runs.

## 7. Acceptance — THE CAPTURE TEST

"Joe, log this one: [board], one pallet, Jacksonville to Tampa, $750, pickup Thursday." →
Joe: "LOGGED. OPPORTUNITY [id]. [board], JACKSONVILLE TO TAMPA, $750, PICKUP THURSDAY."
Verify: record in Spine with driver attribution; audit entry complete; capture-to-LOGGED under 15 seconds; duplicate re-capture of the same load merges rather than doubles; capture attempt with token unset fails closed with honest report.

## 8. Explicitly not in this plan
- No board automation, scraping, screen capture, or session tooling of any kind — capture input is the Owner's eye and voice, period.
- No scoring logic — the engine is Phase 4; until then, captured Opportunities are reviewed by the Owner (Joe may report the raw list on request: THINK class).
- No new blockers — Stage A needs only the token; Stage B needs what Track 1 already needs.
