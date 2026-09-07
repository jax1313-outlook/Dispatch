# DISPATCH CONCEPT OF OPERATIONS
# JOE AS OPERATIONAL CO-DRIVER — DRIVER WORKSTATION + NODE ARCHITECTURE
**Version:** v1.1 — RATIFIED
**Authority:** Mike Zachary, Owner/Operator, Level 1 Transport Inc.
**Ratified:** 2026-09-07 (CONOPS-EVAL v1.0, R1–R9 all ruled; R4 modified per Owner)
**Supersedes:** DRAFT v1.0

---

## 0. Glossary (Owner ruling — R4)

- **Mission Card** = UI representation — the human-facing object (form, tablet display, visor sheet).
- **Opportunity** = Unaccepted mission.
- **Mission Record** = Accepted mission in Dispatch (after BOOK IT).
- "Load Card" retires. Capture in any form writes through the ruled Opportunity contract; origin is metadata.

## 1. Executive Summary

Dispatch operates as a node-and-terminal architecture. The driver interacts with a tablet. Dispatch operates from a laptop node. Joe is a Dispatch capability living on the node, communicating with the driver through the tablet.

The goal is not automation. The goal is cognitive-load reduction for the owner/operator. Joe functions as a digital dispatch clerk and operational co-driver.

**Evaluation questions, answered and ratified:** the node + tablet architecture is correct; Joe is correctly located on the node. The node holds everything ownable — contracts, services, audit, records. The tablet holds the microphone, speaker, and portal. The rented language brain remains in the cloud, per the Rent-the-Trailer Rule.

## 2. Architectural Model

### Dispatch Node
Laptop in ventilated Pelican case within the truck. Responsibilities: Mission Records, Mission Cards, Dispatch workflow, scheduling, COMI, Publisher, Library, Archive, Route Risk, Joe services, MCP services, APIs, audit records. **The node is the operational center of gravity. The node owns workflow and records.**

**Unattended recovery (R5):** the node must survive power loss without a keyboard — BIOS auto-power-on, auto-login, Dispatch services on boot, and a self-test reporting node status to the portal on recovery. A bad bump on I-10 costs seconds, not a roadside IT session.

### Driver Workstation
Cellular-enabled tablet. Responsibilities: phone, microphone, speaker, headset interface, camera, Driver Portal, Mission Card display, Joe interface.

**The tablet is not Dispatch. The tablet is the driver's workstation. The tablet is a portal into Dispatch.**

**Trust boundary (R9):** the tablet holds no records and no standing secrets. Portal sessions authenticate to the node, expire, and are revocable from the node. A stolen tablet is a hardware loss, never a data loss. DISPATCH_JOE_TOKEN never lives on the tablet.

### Connectivity — honest degraded modes (R1, R5)
The tablet provides the cellular connection; the node treats internet as **intermittent by default** — outbound work queues and retries honestly. Mission data remains on the node; internet is required only for external services (email, board APIs, web research, cloud brain).

| Connectivity | Dispatch (node) | Joe voice | Portal (tablet↔node local link) |
|---|---|---|---|
| Online | Full | Full | Full |
| Offline | Full — records, cards, workflow | DOWN — the rented brain is cloud intelligence | Full by touch |

The portal displays Joe's state at a glance in locked vocabulary: **JOE LIVE / JOE DOWN.** Loss of internet never stops local operation; it silences the co-driver's voice until signal returns. Option held open, not built: an independent cellular path for the node (USB modem/router in the Pelican case) if tablet-as-gateway proves limiting in practice.

### Records survivability (R8)
Automated nightly encrypted backup off-node whenever connectivity allows; the append-only audit ships more frequently. Destination: the home NAS. A restore test to a spare machine joins the annual war-reserve-check habit. "Recoverable" and "Portable" are procedures, not adjectives.

## 3. Operational Philosophy

Dispatch owns workflow. The Mission Record owns mission data. Joe supports the driver. Joe never replaces human command authority. Mike remains final authority. Joe performs clerical, coordination, analysis, and communication functions.

## 4. Mission A — Information Capture *(Phase: nearest-term — the ruled Opportunity Capture contract, Stages A/B)*

**Intent:** capture freight opportunity information with minimal cognitive load. Sources: broker calls, shipper calls, existing customers, manual opportunities, Sweeper opportunities. All become an Opportunity via the same contract; origin is metadata.

**Capture legality (R2 — Owner ruling):** in v1, Joe is the **keyboard representative** — the card is filled from the driver's voice alone; no broker audio is processed. The driver echoes key facts aloud as the broker gives them ("Okay — load 4471... Ocala Thursday... $750 all-in"), which is also live confirmation the broker hears. **If and when Joe graduates to live-call capture, a Florida-compliant consent disclaimer is read at the beginning of every call, and the disclaimer event is logged in the audit (timestamp, played, call continued) so consent is provable.**

**Human workflow:**
> Broker: "Mike, I have a load."
> Driver: "Hey Joe, grab a Mission Card."
> Joe: "NEW MISSION CARD OPEN."
Joe opens a blank Mission Card and fills it from the driver's voice: load number, pickup, delivery, consignee, shipper, weight, pieces, equipment, rate, fuel surcharge, detention policy, notes. No keyboard.

**Read-back and VERIFIED (R6):**
> Driver: "Joe, read this back so Mr. Smith can verify."
Joe reads the card; driver and broker verify; corrections are immediate. On completion the card gains **verified: true + timestamp + method (BROKER READ-BACK)** in the audit. Verified cards outrank unverified ones downstream — verification is data, not just courtesy.

**Save:** "Joe, save mission." The Opportunity enters the Dispatch queue.

## 5. Mission B — Operational Analysis *(Phase: arrives in slices — Spine queries Phase 1, calendar Phase 2, full Week Context depth Phase 4)*

> Driver: "Joe, let's talk scheduling."
Joe analyzes existing commitments, calendar, capacity, positioning, schedule conflicts, delivery feasibility, reserve capacity impact, future position opportunities. Joe provides analysis. **Joe does not make the decision. The driver decides.**

## 6. Mission C — Workflow Execution *(Phase: Phase 2 workflows + COMI; the "book it" pipeline per OPPORTUNITY_CAPTURE_PLAN.md §6A)*

> Driver: "Joe, book it."
The Opportunity graduates to a Mission Record. Joe executes approved workflows: acceptance email, rate confirmation, broker packet, carrier packet, onboarding package, COMI routing, calendar updates, mission creation. Joe reports status in declarative voice:
> "RATE CONFIRMATION PREPARED." "BROKER PACKET PREPARED." "READY FOR APPROVAL."
Prepare everything; send nothing without the word — Class 2 discipline throughout.

## 7. Joe Activation Model — session boundary (R3)

Joe is not always active and is not continuously listening. **A wake phrase ("Hey Joe, grab a Mission Card") opens a bounded session; "Joe, save mission," "Joe, stand down," or an Owner-set timeout (default 10 minutes) closes it; between sessions the microphone is dead.** The tablet app implements a wake-word listener plus session windows — never an open mic. Natural-language activation, no menus, no explicit modes. Human factors: cab noise at speed makes a headset or push-to-talk mic the expected capture path; the 70 MPH Test applies to the wake experience.

## 8. Human Factors Goal

The system behaves like a competent dispatch clerk beside the driver. Joe holds the clipboard, captures information, reads back, prepares communications, assists analysis, reduces paperwork. Joe does not replace authority, make business decisions, accept loads autonomously, change doctrine, or override human decisions.

## 9. Relationship to Sweeper

Sweeper is the primary acquisition method; voice capture is secondary; keyboard entry remains available. All three produce the same Opportunity through the same contract:

Sweeper → Opportunity → Dispatch · Voice capture → Opportunity → Dispatch · Keyboard → Opportunity → Dispatch

**Dispatch does not care how the card originated. Only the metadata records origin source.** Deduplication per OPPORTUNITY_CAPTURE_PLAN.md §3: one load, one record, all origins in the audit trail.

## 10. Long-Term Vision

The broker experiences professional information capture, verification via read-back, rapid document preparation, improved communication. The driver experiences reduced cognitive load, reduced typing, reduced administrative burden, increased operational awareness. The system remains Driver First, Mission Record First, platform independent, recoverable (per §2 R8 procedures), portable, and explainable. The architecture remains consistent with Dispatch doctrine.
