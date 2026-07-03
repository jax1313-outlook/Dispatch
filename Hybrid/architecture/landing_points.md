# Hybrid — Landing Points (Just-in-Time Pinning)

The **horizontal constraint** of the build spine: for every artifact in
`workflows/`, `data_model/`, and `templates/`, the **latest step (1–14) by which
it must exist** without breaking any Definition of Done (see `build_sequence.md`).

- **Late = breakage** (an artifact after its pinned step breaks that step's DoD).
- **Early = safe** (front-loading is always allowed).
- **Schema stance = front-load** (all `data_model/` schemas land at Step 2 and are
  frozen thereafter — see `versioning_strategy.md`).

Pinning rule: **an artifact's deadline = the earliest step whose DoD requires it.**

## Section 1 — `data_model/` (hard Step-2 gate)
All schemas land by **Step 2** and are immutable after Step 2.

| Artifact | Latest Step | Notes |
|---|:---:|---|
| `opportunity.json` | 2 | First consumed at 5 (intake), 7 (validation). |
| `vendor.json` | 2 | Contract I5. Consumed at 6/7 (eligibility gating). |
| `capability.json` | 2 | Feeds scoring (9) + proposal tailoring (11). |
| `proposal.json` | 2 | Contract I6 (`packet`). First consumed at 11. |
| `scoring.json` | 2 | Feeds scoring (9); consumed by engines (8)/intelligence (9). |

## Section 2 — `workflows/`

### daily/ — recurring/scheduled → Automation-Lifecycle (Step 13)
| Workflow | Latest Step | Notes |
|---|:---:|---|
| `morning_sweep.md` | 13 | Scheduled acquisition sweep over Step 5. |
| `opportunity_check.md` | 13 | Recurring intake+validation run. |
| `proposal_update.md` | 13 | Recurring status update over in-flight proposals. |
| `compliance_check.md` | 13 | Scheduled eligibility re-check over Step 7 outputs. |

### weekly/ — scheduled → Step 13
| Workflow | Latest Step | Notes |
|---|:---:|---|
| `monday_briefing.md` | 13 | Weekly report; orchestration/reporting. |
| `capability_refresh.md` | 13 | Scheduled refresh of `capability.json` data (schema stays frozen). |
| `data_sync.md` | 13 | Scheduled persistence sync. |
| `template_review.md` | 13 | Meta/governance cadence. |

### opportunity/ — opportunity spine (5→10)
| Workflow | Latest Step | Notes |
|---|:---:|---|
| `intake_workflow.md` | 5 | Step 5 DoD (Acquisition + Email Intake). |
| `validation_workflow.md` | 7 | Step 7 DoD (eligibility_validation) — A4 gate. |
| `scoring_workflow.md` | 9 | Step 9 DoD (hybrid_intelligence scoring). |
| `export_workflow.md` | 10 | Post-decision export of the opportunity record. |

### proposal/ — proposal spine (11→12)
| Workflow | Latest Step | Notes |
|---|:---:|---|
| `generation_workflow.md` | 11 | Step 11 DoD (Proposal Packet). |
| `review_workflow.md` | 11 | Human review branch of the draft packet. |
| `submission_workflow.md` | 12 | Step 12 DoD (Submission). |

### error_handling/ — earliest failure domain
| Workflow | Latest Step | Notes |
|---|:---:|---|
| `missing_data.md` | 5 | First bites at intake; underpins Step 5 degraded-path DoD (and eligibility "unverified" at 7). |
| `invalid_format.md` | 5 | Schema validation first enforced at Step 5. |
| `failed_validation.md` | 7 | Failure/blocker branch of eligibility_validation (Step 7). |
| `retry_logic.md` | 12 | First strictly required at DocuSign poll / submission resend; earlier steps use fallback. |

## Section 3 — `templates/`

### proposals/ — packet content → Step 11
| Template | Latest Step | Notes |
|---|:---:|---|
| `technical_template.md` | 11 | Proposal Packet volume (hard prereq for Step 11). |
| `management_template.md` | 11 | Proposal Packet volume. |
| `past_performance_template.md` | 11 | Proposal Packet volume. |
| `pricing_template.md` | 11 | Proposal Packet volume. |

### capability_statements/ — packet attachments → Step 11
| Template | Latest Step | Notes |
|---|:---:|---|
| `one_page.md` | 11 | Attachment produced during packet build. |
| `two_page.md` | 11 | Attachment. |
| `federal_format.md` | 11 | Attachment. |

### emails/
| Template | Latest Step | Notes |
|---|:---:|---|
| `intake_email.md` | 10 | Decision/notification email at the Control gate. |
| `followup_email.md` | 13 | Lifecycle-driven reminder/follow-up (assumption; →10 if a Control-stage follow-up). |
| `submission_email.md` | 12 | Packet-delivery email at Submission. |
| `confirmation_email.md` | 12 | Post-submission confirmation. |

### boilerplate/ — reusable proposal content → Step 11
| Template | Latest Step | Notes |
|---|:---:|---|
| `company_overview.md` | 11 | Embedded in packet/capability build. |
| `sdvosb_language.md` | 11 | Narrative block (verdict stays deterministic at 7; this is prose only). |
| `compliance_language.md` | 11 | Packet narrative. |

### forms/
| Template | Latest Step | Notes |
|---|:---:|---|
| `cover_letter.md` | 11 | Packet component. |
| `attachments_list.md` | 11 | Packet component. |
| `submission_checklist.md` | 12 | Pre-submission validation/QA gate at Submission. |

## Ranges
- Schemas → **2** (frozen). Workflows → **5–13**. Templates → **10–13**.

## Open assumptions (flagged; correcting either only moves that one row)
1. `followup_email.md` → **13** (lifecycle reminder). If Control-stage follow-up → **10**.
2. `retry_logic.md` → **12** (retry first strictly required at DocuSign/submission).
   If a unified retry layer must also cover acquisition → **5**.

## Governing rule
An artifact produced **later** than its pinned step breaks that step's DoD and is
drift. Produced **earlier** is safe. The `data_model/` Step-2 gate is absolute:
no Step 3–13 module runs against an unschema'd object, and no schema is reshaped
after Step 2.
