# docs/ — Claude-3 Governance Mirror

This directory is a **mirror**, refreshed from the `jax1313-outlook/Claude-3` repository. **Do not edit these files here.** Claude-3 is the canonical source; if doctrine needs to change, it changes there first, then this mirror is refreshed to match.

This import was performed under Stage 2 (Documentation Import) of the Migration Plan defined in Claude-3's `DISPATCH_INTEGRATED_BLUEPRINT_v1.md` §16, following Mike's approval ("Approve Stage 2") recorded in `DISPATCH_BLUEPRINT_DECISION_LOG.md`.

## Files

- **`DISPATCH_CONSTITUTION_v3.md`** — the controlling governance law for all Dispatch development work. If anything in this codebase conflicts with this document, the Constitution controls until Mike approves a replacement.
- **`DISPATCH_FINAL_BLUEPRINT_v1.md`** — the current target architecture: the five-layer model, all six organizational functions (Manager, Publisher, Intelligence Analyst, Library, Archive, Portal), the Dispatch Spine specification, Version Doctrine, Intelligence Verification, Alert Governance, Security, Driver/Broker Portal scope, MVP scope, and the build/deployment path.
- **`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`** — Identity, PIN, Session, Role, Permission, and Audit doctrine. This is the specification Stage 7 (Security Foundation) builds against.
- **`DISPATCH_SPINE_SPECIFICATION_v1.md`** — the deterministic runtime specification: Work Item, Event, Portal Card, Approval Event, Conflict Event, Audit Event schemas, state list, and allowed transitions. This is the specification Stage 4 (Data Engine / Spine Reconciliation) builds against.
- **`LIBRARY_INGESTION_RULE.md`** — governs how documents enter any Library. Human-placed documents are accepted immediately, with no verification/approval/promotion gate; Publisher-generated assets are unaffected and still require review/approval. Also defines the PIN-protected Security sub-library and records the Scanner API integration as a future build item.

- **`STAGE_STATUS.json`** — a small, structured, hand-authored snapshot of `DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md` and `DISPATCH_BLUEPRINT_DECISION_LOG.md`'s current state (per-stage status, dependencies, blocked items, test status, walkthrough reports, and a hand-set recommended next stage). Added under Stage 12 Phase M4 (`DISPATCH_STAGE12_MANAGER_M4_MIRROR_DESIGN_v1.md`) so `dispatch/manager/stage_gate.py` can surface Migration Plan status on the `/manager` Portal page without Manager ever reading Claude-3 doctrine prose or reaching GitHub at runtime. Refreshed manually, as one more step in the same habit that already updates the two Claude-3 documents above after every stage action — not a live integration, and Manager's `/manager` page fails soft (the Stage Gate panel simply doesn't render) if this file is ever missing or out of date with its schema.

## Relationship to `CLAUDE.md`

This repository's own `CLAUDE.md` (repo root) remains the authoritative spec for the existing CIN-Lite pipeline's five layers (Acquisition / Processing / Control / Archive / Automation). That model is **not the same** as the five layers in `DISPATCH_FINAL_BLUEPRINT_v1.md` (Authority / Presentation / Organizational / Deterministic / Cognitive) — the two are reconciled in Claude-3's `DISPATCH_INTEGRATED_BLUEPRINT_v1.md` §9, and will be cross-referenced directly in `CLAUDE.md` under Stage 3 (Blueprint Alignment), not yet performed as of this import.

## What This Import Does Not Do

Copying these files here does not itself change any code, behavior, or deployment state of this repository. No stage past Stage 2 (Documentation Import) has been approved as of this commit. See `DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md` in Claude-3 for the full staged plan and current status.

Mike Zachary remains final authority. Mike decides.
