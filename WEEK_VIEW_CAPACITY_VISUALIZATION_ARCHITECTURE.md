# WEEK VIEW CAPACITY VISUALIZATION ARCHITECTURE

> **HOS / ELD boundary (Operational Readiness Mission, Section 1.6).** Dispatch is not an
> ELD and holds no hours-of-service data. There is no ELD, GPS, or telematics integration
> anywhere in the program, and none is configured. Every reference to HOS below describes
> either (a) a value **estimated** from distance and appointment windows, or (b) a
> capability that would require a live trusted external source that does not exist today.
> The driver is responsible for legal HOS compliance. Nothing in this document is a
> readiness claim that Dispatch knows a duty clock. Where an HOS value is displayed, it is
> labeled as an estimate at the surface.


**Document Type:** Architecture Specification
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Operator Awareness & Capacity Visualization

---

## 1. Executive Summary

Week View is **NOT** a dispatch board, planning board, or scheduling system.
Week View **IS** a **Capacity Visualization** tool.

Purpose:
> Allow the owner/operator to instantly see operational capacity and schedule gaps for awareness, not for automated planning.

---

## 2. Visualization Components

Week View presents five key operational indicators across a rolling 7-day or 14-day window:

1. **Available Capacity:** Uncommitted time windows, estimated drive-time headroom (not a duty-clock reading — Dispatch holds none), and unallocated equipment space where new freight can be accepted.
2. **Consumed Capacity:** Fully committed time, driver duty hours, and trailer space assigned to active/scheduled loads.
3. **Reserve Capacity:** Intentionally held safety buffers (e.g., a 2-hour drive-time reserve for weather/traffic, maintenance inspection buffers). The reserve is a planning allowance, not a measured remaining duty clock.
4. **Position Capacity:** Anticipated geographic truck location at the end of each committed load (e.g., "Inbound Chicago Friday 14:00").
5. **Schedule Gaps:** Unplanned dead time, deadhead traps, or utilization gaps where asset generation is zero.

---

## 3. Operational Rules

1. **Awareness, Not Execution:**
   - Week View provides instant situational awareness for the owner/operator.
   - It does not automatically drag-and-drop or auto-assign opportunities onto days.

2. **Single Source of Truth Alignment (D4):**
   - Consumed capacity shown in Week View is derived directly from canonical committed loads on the Calendar.
   - Week View presents reality; it does not maintain separate duplicate schedule records.

3. **70 MPH Test & Cognitive Load (D2, D3):**
   - Color-coded visual clarity: Green = Available Capacity, Blue = Consumed/Committed, Orange = Reserve Buffer, Red = Schedule Gap / Deadhead Trap.
   - Allows the driver/operator to assess week balance at a glance within seconds.
