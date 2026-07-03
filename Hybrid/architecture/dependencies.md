# Hybrid — Dependency Map

## Layering rule (allowed direction)
A layer may depend **downward/inward** only. Upward calls happen via events/return
values, never direct imports.

```
Automation/Lifecycle
        │  may use
        ▼
Intake ▶ Eligibility ▶ Intelligence ▶ Decision ▶ Generation ▶ Execution
        └───────────────┬───────────────┬───────────────┘
                        ▼               ▼
                  Persistence  ◀───  Governance/Config
        (any layer may read config + write archive/audit; neither depends on a business layer)
```

## Module dependency graph (DAG)
```
config ──────────────┐ (read by all)
audit_log ◀──────────┼─ (written by all; depends on nothing)
                     │
vendor_profile ◀── engines ◀── hybrid_intelligence ◀── (owner) HybridOrchestrator
     ▲                 ▲                                     │
     │                 │                                     ▼
acquisition        set_aside_eligibility ───────────────▶ control
     │                 ▲                                     │
email_intake ─────────┘                                     ▼
                                                    proposal_packet
                                                          │
                                                     signature ─▶ submission
                                                          │
lifecycle ◀───────────────(observes all step events)─────┘
ownership_guard ─(gates)▶ hybrid_intelligence access
```

## Key dependencies (who needs whom)
| Module | Depends on |
|--------|-----------|
| `acquisition` / `email_intake` | `config` |
| `vendor_profile` | `config` |
| `set_aside_eligibility` | `vendor_profile`, external E2/E3, `config` |
| `engines` | `vendor_profile`, `CINRouter` |
| `hybrid_intelligence` | `engines`, `set_aside_eligibility` (signals) |
| `HybridOrchestrator` (owner) | `hybrid_intelligence`, `ownership_guard` |
| `control` | `hybrid_intelligence` output, `config` |
| `proposal_packet` | `vendor_profile`, `intelligence`, `templates/` |
| `signature` | `proposal_packet`, DocuSign (E6) |
| `submission` | `signature` output, Outlook/portal (E5) |
| `lifecycle` | events from all layers (no reverse import) |
| everything | `config` (read), `archive`/`audit_log` (write) |

## External dependency inventory
- **Runtime:** Python stdlib (portable core). Optional: `anthropic` (agents),
  `requests` (Graph/DocuSign). Everything else stdlib-only.
- **Services:** SAM.gov (E1), VetCert/CVE (E2), SBA size table (E3), Claude (E4),
  Graph (E5), DocuSign (E6), SMTP (E7). All have degraded-mode fallbacks.

## Architectural invariants (must not be violated)
1. **No business layer imports upward.** Lifecycle observes via events.
2. **Intelligence is produced only behind the ownership guard.**
3. **`audit_log` and `config` are dependency sinks/sources** — they never depend
   on a business module (keeps them safe to call everywhere).
4. **External adapters are leaf nodes** — swapping SAM/DocuSign/Outlook/portal must
   not ripple past the module that owns that integration.
