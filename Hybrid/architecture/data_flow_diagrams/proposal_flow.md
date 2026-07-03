# Data Flow — Proposal Generation → Submission

Begins when `control` records `approve_proposal` (end of `opportunity_flow.md`).
Driven by the lifecycle state machine.

```
 approve_proposal ─▶ proposal_packet.build ─▶ [packet: forms, attachments, pdf_path]
                                │  state: generated
                                ▼
                        control (human review) ◀── human
                                │  state: awaiting_review
                                ▼
                        signature (DocuSign)
                          ├─ send_to_docusign   → state: external_edit_in_progress
                          ├─ wait_for_completion → (poll)
                          └─ retrieve_signed     → state: ready_for_submission
                                │
                                ▼
                        submission (Outlook/portal) → state: submitted
                                │
                                ▼
                        archive + audit_log  (packet, receipt, versions)
```

## Lifecycle states
`loaded → generated → awaiting_review → awaiting_external_edit →
external_edit_in_progress → ready_for_submission → submitted`
(terminal branches: `rejected`, `sign_stalled`, `submission_failed`).

## Step table
| Step | Module | Input | Output | State |
|------|--------|-------|--------|-------|
| 1 | `proposal_packet.build` | opportunity + profile + intelligence | draft packet | generated |
| 2 | `control` | draft packet | human review outcome | awaiting_review |
| 3 | `signature.send` | packet.pdf_path, signer | envelope id | external_edit_in_progress |
| 4 | `signature.wait` | envelope id | completion status | — |
| 5 | `signature.retrieve` | envelope id | signed pdf | ready_for_submission |
| 6 | `submission` | signed packet, recipient | receipt | submitted |
| 7 | `archive` | packet + receipt + versions | persisted | (terminal) |

## Invariants
- No packet enters `signature` without a human review outcome (step 2).
- Signed artifact **replaces** the draft via a new packet `version` (never in place).
- Submission adapter is pluggable (email now; portal adapter is a NEW integration).
