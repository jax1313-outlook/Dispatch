# Data Flow — Opportunity Intake → Decision

From discovering an opportunity to a recorded human decision. (Proposal execution
continues in `proposal_flow.md`; eligibility detail is in `validation_flow.md`.)

```
 SAM.gov / Email ─▶ acquisition ─▶ [normalized opportunity]
                                        │
                                        ▼
                         set_aside_eligibility ──▶ [eligibility_verdict]
                                        │                 │ eligible == false
                                        │ eligible/soft   └────────────▶ archive (ineligible) + log
                                        ▼
        vendor_profile ─────────▶ CINRouter.dispatch ─▶ engines ─▶ [findings]
                                        │
                                        ▼
                         HybridOrchestrator.run_intelligence  (guarded)
                                        │
                             [intelligence: summary, scoring, rules, routing]
                                        │
                                        ▼
                              control (checkbox email)  ◀── human
                                        │
                        recorded action ─▶ route ─▶ archive + audit_log
                                        │
                        action == approve_proposal ─▶ proposal_flow.md
```

## Step table
| Step | Actor / module | Input | Output | Stored |
|------|----------------|-------|--------|--------|
| 1 | `acquisition` | source config | normalized opportunity | Raw |
| 2 | `set_aside_eligibility` | opportunity + vendor_profile | eligibility_verdict | Processed |
| 3 | (gate) | eligibility_verdict | continue OR archive-ineligible | Routing |
| 4 | `vendor_profile` | vendor id | vendor_profile | — |
| 5 | `engines` via CINRouter | opportunity + profile | per-domain findings | Intelligence |
| 6 | `HybridOrchestrator` | findings + verdict | intelligence product | Intelligence |
| 7 | `control` | intelligence + summary | human action → route | Routing |
| 8 | `archive`/`audit_log` | action, route | persisted decision | Routing/Logs |

## Rules & invariants
- Eligibility gate (step 3) can hard-stop before any scoring cost.
- Intelligence is produced **only** by the Intelligence Owner (step 6).
- The decision (step 7) is logged **before** any file is moved/routed.
