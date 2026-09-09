# DISPATCH WORKER CONSTITUTION ARCHITECTURE

**STATUS: WORKING DRAFT / DISCOVERY / NOT DOCTRINE**

Authored by Mike. Brought into the repository ahead of the tab walk so the walk has a
stable reference. This document authorizes no code, no route, no data model, and no
runtime behavior. It is the lens the tab walk looks through, not a build order.

Where its vocabulary meets existing doctrine, see `docs/tab-walk/LENS.md`. That file
records what Mike has settled and what is still open. It resolves nothing on its own.

Two things below have already moved. Mike has ruled that JOE is no longer optional, and
that department-named separation of process is superseded by agents whose Level is not yet
determined. The text here is preserved as written. LENS.md carries the rulings.

---

## Discovery

A review of agent-oriented architecture concepts revealed that the most valuable insight
was not the concept of AI agents themselves, but the concept of defined worker
relationships and handoffs.

Dispatch already contains bounded workers. The missing architectural artifact is a formal
definition of how work moves between workers and under what conditions a handoff occurs.

The system should not depend on workers inventing the next step. The system should
explicitly define who receives the work package next.

This mirrors how real offices operate.

---

## Level 0 — Base Constitution

Defines:

- Human authority
- Mission Record doctrine
- Dispatch Independence doctrine
- Authority boundaries
- Ownership model
- System-wide rules

Answers: **What rules govern everyone?**

## Level 1 — Worker Constitutions

Defines:

- Identity
- Purpose
- Capabilities
- Boundaries
- Inputs
- Outputs
- Relationships
- Handoffs

Answers:

- Who am I?
- What am I allowed to do?
- What do I receive?
- What do I produce?
- Who gets it next?

Workers currently include: Joe, Intelligence, Publisher, Library, Archive, Dispatch.

## Level 2 — Workflow / State Transitions

Defines operational flow. Not screens. Not software. Business state transitions.

```
Opportunity Discovery
        ↓
Opportunity Analysis
        ↓
Human Review
        ↓
Commitment
        ↓
Commitment Package
        ↓
Mission
        ↓
Execution
        ↓
Closeout
        ↓
Archive
```

Answers: **What state is the business in?**

## Level 3 — Portals / Screens

Defines views. Examples: Booking Screen, Calendar, Driver Portal, Operations Portal.

Answers: **How does the human see the workflow?**

Screens are presentation layers. They do not define workflow.

---

## Worker definition example — Intelligence Worker

**Purpose.** Own the entire pre-commit lifecycle.

**Receives.** DAT loads, Truckstop loads, voice opportunities, manual opportunities,
external intelligence.

**Performs.** Collection, analysis, route analysis, risk analysis, opportunity
evaluation, opportunity scoring, recommendation generation.

**Produces.** Opportunity Card, findings, recommendations, calendar placement
recommendations, calendar hole visibility.

**Handoff.** To Mike, on the condition that the opportunity is fully analyzed and ready
for review.

**Boundary.** May recommend. May not commit.

## Worker definition example — Publisher Worker

**Purpose.** Own the commitment package lifecycle.

**Receives.** Committed load, broker requirements, customer requirements, relationship
information, Library assets.

**Performs.** Document assembly, communication creation, package construction,
requirement validation.

**Library relationship.** May retrieve W-9, COI, carrier packet components, customer
packet components, templates, approved language.

**Archive relationship.** May retrieve previous examples, historical artifacts, prior
communications. May submit completed communications, completed packages, completed
artifacts.

**Produces.** Commitment package, broker communications, customer communications, load
documentation.

**Boundary.** May produce. May not commit.

---

## Important discovery

The booking screen is not merely a booking screen. It is an Intelligence presentation
surface.

The purpose is not to display opportunities in a list. The purpose is to display
opportunities in the context of future capacity.

Not: here are 50 loads.

But: here is a load that fits the Jacksonville-to-Tampa opening on the 18th.

The calendar is therefore part of the decision-support process.

## State transition discovery

The transition does not occur when Intelligence finishes. The transition occurs when Mike
commits.

At that moment the calendar slot is selected, the Outlook event is created, capacity is
consumed, and the opportunity ceases to be an opportunity.

```
Opportunity Card
        ↓
Committed Load
```

Publisher then executes the commitment package. After commitment communications are
prepared and sent:

```
Committed Load
        ↓
Load Card / Mission Record
```

Dispatch receives the committed mission and executes deterministically from that point
forward.

---

## Core takeaway

The most important discovery is that workers should not be expected to determine where
work goes next. That must be explicitly defined.

A worker constitution must include identity, capabilities, boundaries, inputs, outputs,
relationships, and handoffs.

The Constitution tells a worker: **Who am I?**

The Relationship portion of the Constitution tells a worker: **when you are done, where
does the folder go next?**
