# DISPATCH DYNAMIC CAPACITY ARCHITECTURE

> **HOS / ELD boundary (Operational Readiness Mission, Section 1.6).** Dispatch is not an
> ELD and holds no hours-of-service data. There is no ELD, GPS, or telematics integration
> anywhere in the program, and none is configured. Every reference to HOS below describes
> either (a) a value **estimated** from distance and appointment windows, or (b) a
> capability that would require a live trusted external source that does not exist today.
> The driver is responsible for legal HOS compliance. Nothing in this document is a
> readiness claim that Dispatch knows a duty clock. Where an HOS value is displayed, it is
> labeled as an estimate at the surface.


**Document Type:** Core Architecture Specification
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Dispatch Spine Engine (`dispatch/capacity.py`)

---

## 1. Executive Summary

Dynamic Capacity is a first-class Dispatch Spine object.
- It is **NOT** a scheduler feature.
- It is **NOT** a portal widget.
- It is a core operational model and reusable engine across all Dispatch sub-systems.

Dynamic Capacity models the operational ability of an asset (truck/trailer/driver unit) to accept work across time, space, physical dimensions, regulatory constraints, and cargo arrangements.

---

## 2. Core Operational Dimensions

Dynamic Capacity evaluates capacity across six primary dimensions:

```
Dynamic Capacity
├── Physical Capacity
├── Time Capacity
├── Position Capacity
├── Reserve Capacity
├── Cargo Arrangement Capacity
└── Stop Sequence Capacity
```

### 2.1 Physical Capacity
- **Max Weight & Remaining Weight Payload:** Gross vehicle weight rating (GVWR) limits vs. net loaded cargo weight.
- **Max Volume / Linear Feet / Pallet Count:** Available floor space, door height/clearance, cubic capacity.
- **Equipment Type Capabilities:** Dry Van, Reefer (temperature zone control), Flatbed, Step Deck, Liftgate equipped, Ramp equipped.

### 2.2 Time Capacity
- **Hours of Service (HOS):** Available driving hours, duty window, 10-hour reset schedules, 34-hour restart requirements.
- **Appointment / Window Constraints:** Pickup and delivery window feasibility given driver HOS and transit speeds.
- **Transit & Dwell Allowance:** Speed limits, expected traffic buffers, loading/unloading detention allowances.

### 2.3 Position Capacity
- **Current Geographic Location:** GPS coordinate / City, State origin of truck.
- **Deadhead Distance & Time:** Cost and time required to reach pickup point.
- **Destination Market Quality / Relocation Value:** Position created by delivery location (e.g., re-positioning into a high-rate outbound lane vs. a deadhead trap).

### 2.4 Reserve Capacity
- **Safety Buffers:** Reserved HOS hours for traffic, weather, or unexpected detention delays.
- **Weight / Space Buffers:** Unallocated weight/space kept in reserve for unexpected partial additions or emergency freight.
- **Flexibility Thresholds:** Maintenance inspection buffers and regulatory compliance margins.

### 2.5 Cargo Arrangement Capacity
- **Load Geometry & Stacking:** Physical arrangement constraints (Single Pallet, Multi Pallet, Partials, Mixed Freight, Stacked vs. Non-Stacked).
- **Handling Constraints:** Liftgate requirement, pallet jack requirements, hazardous material segregation, temperature control zones.

### 2.6 Stop Sequence Capacity
- **Multi-Stop Logistics:** LIFO (Last-In-First-Out) loading constraints vs. intermediate pickups/deliveries.
- **Route Optimization & Out-of-Route Miles:** Feasibility of adding intermediate stops without violating pickup/delivery appointments or driver HOS.

---

## 3. Subsystem Consumers

Dynamic Capacity is designed to be fully reusable across all Dispatch systems and services:

1. **Intelligence Intake:** Filters out opportunities that exceed baseline physical or time limits.
2. **Analysis:** Calculates deadhead, HOS impact, and out-of-route margins for opportunities.
3. **Score Engine:** Penalizes tight time windows or poor destination positioning; rewards high capacity utilization.
4. **Filters / Sort:** Allows operators to filter opportunities by remaining weight, required liftgate, or location.
5. **Opportunity Cards:** Displays capacity consumption (e.g., "Consumes 45% HOS, 80% Weight, Relocates to Chicago").
6. **Scheduler & Calendar:** Validates that committed loads do not over-commit physical asset capacity or legal HOS limits.
7. **Pricing Engine:** Adjusts rate targets based on capacity scarcity and relocation positioning value.
8. **Revenue Projection:** Calculates potential yield per unit of consumed time/space capacity.
9. **Routing / Route Risk:** Integrates corridor risk and weather delays into dynamic time capacity adjustments.

---

## 4. Operational Rules & Constraints

1. **Reality Bound:** Dynamic Capacity calculation for State 1 (Reality) must be rooted in asset states whose provenance is recorded. Today that means assigned load weight/volume and operator-entered asset configuration. Driver HOS and truck GPS are listed here as *intended future inputs from a live trusted external source*; no such source exists, so `capacity.py` refuses to treat an HOS snapshot as `VERIFIED` without an explicit named source and a timezone-aware observation time, and `UNKNOWN`/`UNAVAILABLE` HOS makes the drive-hours comparison unavailable rather than optimistic.
2. **Simulated Capacity for Possibilities:** In State 2 (Possibilities), Dynamic Capacity evaluates hypothetical consumption without mutating actual current capacity.
3. **No Autonomous Allocation:** Dynamic Capacity reports available and consumed metrics; it does **NOT** automatically assign or lock capacity without explicit owner/operator commitment.
