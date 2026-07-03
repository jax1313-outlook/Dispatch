# Data Flow — SDVOSB Eligibility & Validation

How an opportunity is screened for SDVOSB eligibility/fit (feeds step 2–3 of
`opportunity_flow.md`) and how artifacts are validated before submission.

## Eligibility screen (per opportunity)
```
 opportunity + vendor_profile
        │
        ▼
 set_aside_eligibility
   ├─ set-aside detection      (opportunity set-aside == SDVOSB/VOSB/… ?)
   ├─ VetCert / CVE status     (is the vendor a verified SDVOSB?)          [E2]
   ├─ NAICS + size standard    (vendor size ≤ threshold for opp NAICS?)    [E3]
   ├─ limitations on subcontracting (self-performance feasible?)
   └─ JV / mentor-protégé      (eligible via JV/MP structure?)
        │
        ▼
 [eligibility_verdict]
   eligible: true|false|unverified
   basis:    which checks passed
   blockers: hard failures (e.g., not a set-aside we qualify for)
   signals:  soft flags feeding scoring (e.g., size unverified)
```

## Verdict → downstream
| Verdict | Effect |
|---------|--------|
| `false` (hard blocker) | archive as ineligible; stop (no scoring) |
| `unverified` (soft) | continue; `signals` lower confidence in scoring/routing |
| `true` | continue to intelligence; eligibility recorded as a positive signal |

## Artifact validation (pre-submission QA)
```
 packet ─▶ validation checks ─▶ [validation_report]
   ├─ required forms present
   ├─ attachments complete (certs, capability statement)
   ├─ signature present & envelope completed
   └─ recipient/target resolved
        │  fail → lifecycle: submission_blocked
        ▼  pass
     submission
```

## Step table
| Step | Module | Input | Output |
|------|--------|-------|--------|
| 1 | `set_aside_eligibility` | opportunity + profile | eligibility_verdict |
| 2 | (gate) | verdict | continue / archive-ineligible |
| 3 | validation (QA) | packet | validation_report |
| 4 | (gate) | validation_report | submit / block |

## Invariants
- Eligibility is deterministic and **auditable** (no LLM in the verdict path).
- `unverified` never silently becomes `true`; it is carried as an explicit signal.
- Concrete check definitions and thresholds live in `data_model/` and `workflows/`
  (owned outside this role); this document defines only the flow and contracts.
