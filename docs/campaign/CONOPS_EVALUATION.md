# CONOPS EVALUATION — JOE AS OPERATIONAL CO-DRIVER, NODE + TABLET
**Designation:** CONOPS-EVAL v1.0 (evaluates DRAFT v1.0)
**Evaluator:** Claude, at Owner request
**Date:** 2026-09-07
**Format:** Numbered recommendations R1–R9. Each can be ruled by voice: "Approve R1," "Reject R4," "Modify R2: ..." Approved items fold into CONOPS v1.1.

---

## Verdict

Architecture: SOUND. Both evaluation questions answered yes — node owns workflow and records, tablet is a replaceable portal, Joe's services belong on the node. Doctrine consistency: PASS — nothing in the draft contradicts the ratified mission documents; §9 (origin-agnostic cards) independently restates the ruled dedup doctrine, and Mission C's "READY FOR APPROVAL" is Class 2 behavior stated correctly. The draft is feasible. The recommendations below close gaps, not flaws of concept.

## Strengths worth preserving verbatim
- "The tablet is not Dispatch. The tablet is the driver's workstation." — the whole architecture in two lines.
- The broker-facing read-back (Mission A) — verification as customer-visible professionalism.
- "Dispatch should not care how the card originated. Only the metadata should record origin source."
- The activation examples in §7 — natural language, no modes, no menus.

---

## R1 — Honest degraded-mode matrix (corrects §2 Connectivity)
"Loss of internet should not stop local operation" is true for Dispatch, not for Joe's voice — the language brain is rented cloud intelligence. State the modes plainly so a dead zone never surprises the driver:

| Connectivity | Dispatch (node) | Joe voice | Portal (tablet↔node, local link) |
|---|---|---|---|
| Online | Full | Full | Full |
| Offline | Full — records, cards, workflow | DOWN — reports honestly on loss if possible, silent otherwise | Full by touch |

Corollary: the tablet app must show connectivity state at a glance (Joe LIVE / Joe DOWN), in the locked vocabulary.

## R2 — Echo capture for Mission A v1 (legal guardrail — requires ruling)
Live processing of the broker's side of a call is functionally call recording; Florida requires all-party consent, and violation is criminal exposure, not a ToS matter. Rule one of:
- **(a) RECOMMENDED — Echo capture v1:** Joe listens only to the driver. Driver repeats key facts aloud as the broker gives them ("Okay — load 4471... Ocala Thursday... $750 all-in"); Joe fills the card from driver voice alone. No broker audio processed, no consent needed, broker hears live confirmation (fewer errors on their end). Broker-facing read-back survives unchanged.
- **(b) Consent capture:** full-conversation capture only after explicit on-call consent, captured in the audit record. May be added later as an option on top of (a).

## R3 — Session boundary specification (reconciles §7 with Mission A)
"Not continuously listening" and "follows the conversation" coexist only with a defined session window: wake phrase ("Hey Joe, grab a Mission Card") opens a bounded capture session; "Joe, save mission," "Joe, stand down," or a timeout (suggest 10 min, Owner-set) closes it; between sessions the microphone is dead. State it in the CONOPS — it defines the tablet app's actual audio architecture (wake-word listener + session windows, never open mic) and it protects the driver's own privacy in the cab. Human-factors note: cab noise at speed makes a headset/push-to-talk mic the likely reality for capture quality; the 70 MPH Test applies to the wake experience.

## R4 — Vocabulary unification (one glossary line)
The draft uses Load Card and Mission Card; the ratified documents use Opportunity (pre-decision) graduating to Mission Record (post-"book it"). Proposed glossary: **Mission Card = the form/UI representation; Opportunity = an unbooked card; Mission Record = a booked card in the Spine. "Load Card" retires.** Mission A's capture writes through the same ruled seventh contract (`POST /api/joe/opportunity`) — the broker call is a second *source*, not a second system; the board-listing dictation and the call capture are one capability with two origins.

## R5 — Node connectivity and unattended recovery (hardens §2)
Two single points of failure in the draft:
- **Tablet-as-gateway:** when the tablet leaves the truck (driver walks into a shipper's office), the node loses internet mid-task. Options: accept it (degraded mode per R1 — cheapest), or give the node its own path (USB cellular modem or small router in the Pelican case — modest monthly cost, node independence). Recommend at minimum designing for it: node treats internet as intermittent by default, queues outbound work, retries honestly.
- **Unattended recovery:** a node in a Pelican case must survive power loss without a keyboard: BIOS auto-power-on, auto-login, Dispatch services on boot, and a self-test that reports node status to the portal on recovery. One bad bump on I-10 should cost seconds, not a roadside IT session.

## R6 — VERIFIED as a recorded state (extends Mission A read-back)
The broker-verified read-back is too valuable to leave informal. Proposed: a card gains `verified: true` + timestamp + method (BROKER READ-BACK) in the audit when the read-back completes. Downstream, verified cards outrank unverified ones — the Decision Engine and the paperwork workflows can trust them differently. Verification becomes data, not just courtesy.

## R7 — Phase mapping (grounds §§4–6 against the ratified campaign)
The three missions land at different times; the CONOPS should say so to stay honest about sequencing:
- **Mission A (capture):** contract ruled and planned — Stage A/B per OPPORTUNITY_CAPTURE_PLAN.md. Nearest-term.
- **Mission B (analysis):** THINK class — needs Spine queries (Phase 1, built) + calendar (Phase 2) + Week Context engine (Phase 4 for full depth). Arrives in slices.
- **Mission C (execution):** Phase 2 workflows (templates, email, rate con) + COMI routing. The "book it" pipeline already specified in §6A of the capture plan.

## R8 — Records survivability (makes "Recoverable" concrete)
The node is the single home of operational records in a vehicle — theft, crash, and water are ordinary risks. Recommend: automated nightly encrypted backup off-node whenever connectivity allows, plus the append-only audit shipped more frequently. Natural destination: the home NAS project — giving that build a mission tie-in. Recovery test (restore to a spare machine) belongs in the war-reserve-check habit. "Recoverable" and "Portable" in §10 become procedures, not adjectives.

## R9 — Tablet trust boundary (security note)
The tablet is the most losable device in the system. It must hold no records (already the design) and no standing secrets: portal sessions authenticate to the node, expire, and are revocable from the node ("Joe, kill the tablet session" — or the portal's admin page). A stolen tablet should be a hardware loss, never a data loss. The `DISPATCH_JOE_TOKEN` never lives on the tablet.

---

## Disposition sheet (for dictated rulings)
- **R1 degraded-mode matrix — ✅ RULED 2026-09-07:** understood and accepted; Joe voice stops when connectivity drops; matrix goes in CONOPS v1.1.
- **R2 capture legality — ✅ RULED 2026-09-07 (hybrid):** v1 Joe operates as keyboard representative — filled by driver voice only, no broker audio processed. If and when Joe graduates to live-call capture, a Florida-compliant consent disclaimer is read at the beginning of every call; the disclaimer event is itself logged in the audit (timestamp, played, call continued) so consent is provable.
- **R3–R9 — ✅ ALL APPROVED 2026-09-07**, with R4 modified per Owner: **Mission Card = UI representation (human-facing object); Opportunity = unaccepted mission; Mission Record = accepted mission in Dispatch (after BOOK IT).** All rulings folded into CONOPS_v1.1.md — this evaluation is CLOSED.
