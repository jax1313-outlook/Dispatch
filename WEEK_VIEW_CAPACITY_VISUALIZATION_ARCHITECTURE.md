# WEEK VIEW CAPACITY VISUALIZATION ARCHITECTURE

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

1. **Available Capacity:** Uncommitted time windows, available driver HOS, and unallocated equipment space where new freight can be accepted.
2. **Consumed Capacity:** Fully committed time, driver duty hours, and trailer space assigned to active/scheduled loads.
3. **Reserve Capacity:** Intentionally held safety buffers (e.g., 2 hours HOS reserve for weather/traffic, maintenance inspection buffers).
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
