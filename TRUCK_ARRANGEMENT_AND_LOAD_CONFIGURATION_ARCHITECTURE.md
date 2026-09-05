# TRUCK ARRANGEMENT AND LOAD CONFIGURATION ARCHITECTURE

**Document Type:** Technical & Data Architecture Specification
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Operational Intelligence & Cargo Data Structures (`dispatch/truck_arrangement.py`)

---

## 1. Executive Summary

Truck Arrangement is **operational data**, not merely documentation or static text notes.
It represents the physical, spatial, and handling arrangement of cargo within a transport unit.

Truck Arrangement influences:
- Dynamic Capacity Calculations
- Scheduling & Appointment Buffers
- Opportunity Scoring & Noise Reduction
- Rate Pricing Models
- Revenue Projection & Margin Analysis

*Note:* Implementation focuses on data structures, schema, and API representation. Diagram/graphic generation features are out of scope for this architecture phase.

---

## 2. Cargo Arrangement Structures

The architecture defines and models nine core cargo arrangement structures:

1. **Single Pallet:** Standard single pallet position load (FTL or LTL).
2. **Multi Pallet:** Multiple pallet positions with specific row/column layout requirements.
3. **Partials:** Partial truckload space sharing (occupying defined linear footage or volume).
4. **Mixed Freight:** Combination of various commodity types, packaging, or handling constraints in one trailer.
5. **Stacked:** Vertical stacking permitted (doubling capacity utilization for lightweight cargo).
6. **Non-Stacked:** Vertical stacking prohibited due to fragile, high-value, or top-heavy cargo.
7. **Courier:** Small package, high-density, expedited courier freight configurations.
8. **Liftgate:** Freight requiring hydraulic liftgate loading/unloading (no dock available).
9. **Multi-Stop:** Sequential cargo arrangement ordered according to LIFO (Last-In-First-Out) multi-stop drop-offs.
10. **Custom Arrangements:** Extensible custom cargo configuration specs.

---

## 3. Core Data Structure (`TruckArrangement`)

The canonical dataclass structure captures physical, handling, and operational metrics:

```python
@dataclass
class TruckArrangement:
    arrangement_id: str
    arrangement_type: str        # e.g., single_pallet, multi_pallet, partials, mixed, stacked, non_stacked, courier, liftgate, multi_stop, custom
    pallet_count: int
    linear_feet: float
    total_weight_lbs: float
    total_volume_cuft: float
    is_stackable: bool
    requires_liftgate: bool
    requires_pallet_jack: bool
    requires_temperature_control: bool
    temp_target_fahrenheit: float | None
    stop_sequence_lifo: bool
    special_handling_notes: str
```

---

## 4. Operational Influence Across Dispatch Subsystems

### 4.1 Capacity Engine
- Deducts linear feet and total weight from physical asset capacity.
- Checks stackability flag when calculating remaining volumetric trailer space.

### 4.2 Scoring Engine
- Evaluates operational difficulty: penalizes complex non-stacked multi-stop partials unless rate-per-mile (RPM) premium compensates.
- Rewards liftgate-compatible loads if equipment has active liftgate.

### 4.3 Pricing Engine
- Applies premium multipliers for specialized handling (liftgate, multi-stop LIFO, non-stackable space lockouts).

### 4.4 Scheduler & Routing
- Adds loading/unloading dwell time buffers for multi-stop or liftgate arrangements.
