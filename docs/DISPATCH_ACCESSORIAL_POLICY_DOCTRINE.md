# DISPATCH ACCESSORIAL POLICY DOCTRINE

Status: DOCTRINE. Issued by the operator, 30 August 2026. Supersedes the `accessorials`
block previously drafted into `DISPATCH_POLICY_PROFILE_SPEC.md`.

---

## 1. Accessorials are company policy, not application settings

**They are not hard-coded application settings. They are not scoring-engine constants.**

They live in:

```
Company Library
└── Accessorial Policies
    ├── Detention Policy
    ├── Layover Policy
    ├── TONU Policy
    ├── Lumper Policy
    ├── Liftgate Policy
    └── After-Hours Policy
```

An earlier draft of the Policy Profile carried `accessorials` as a block of numbers beside
the rate floor. **That was wrong.** A detention rate is not a tuning value — it is an
approved company position with a version, an effective date, and an approval history, and
it is quoted to customers.

## 2. Ownership

| Component | Owns | Does not |
|---|---|---|
| **Library** | The authoritative approved policy, prior versions, effective dates, approval history | Calculate the charge |
| **Publisher** | Retrieving the policy, the deterministic calculation, customer-facing wording, drafts and approval packages | Activate or approve policy |
| **JOE** | Receiving the request, activating the workflow, speaking the result, initiating routing, reporting status | Own the policy or perform the authoritative calculation |
| **COMI** | Routing the approval communication, tracking its state, recording the response | Calculate or approve |
| **Email Helper / Outlook** | Preparing, routing and carrying the actual approval message | Decide anything |
| **Mike Zachary** | **Approval** | — |

**JOE may create policy-change requests. JOE may not approve policy changes.** Human
authority remains the approval authority.

## 3. The policy-change workflow

```
Human Request → JOE → Publisher Draft → COMI Routing → Outlook Approval
   → Human Approval → Library Update → Policy Activated
```

**No policy value becomes active merely because Mike requested that a draft be created.**

## 4. Detention — business purpose

Detention is an **opportunity-cost recovery mechanism**. It is not a generic
industry-standard fixed fee.

It represents the productive revenue opportunity lost while the truck is prevented from
moving, plus a punitive amount for disruption and missed opportunity. It exists to:

- recover the value of lost productive capacity
- recover lost productivity
- **influence customer behaviour** by making avoidable delay economically undesirable

Level 1 Transport learned from prior FedEx Custom Critical contracting experience that a
meaningful detention charge encourages shippers and receivers to prioritise the truck and
complete loading or unloading efficiently.

**The customer sees the approved rate. The customer does not need to see the formula.** The
internal calculation remains private unless Mike explicitly authorises disclosure.

## 5. The formula

| Variable | Meaning |
|---|---|
| `M` | Realistic productive miles the truck could travel in sixty minutes |
| `R` | Current approved realistic revenue rate per mile |
| `P` | Punitive missed-opportunity factor |
| `H` | Calculated detention charge per hour |
| `Q` | Calculated detention charge per fifteen-minute increment |

```
H = (M × R) × (1 + P)
Q = H ÷ 4
```

**Formula structure belongs in policy. Values belong in policy. Code belongs in Publisher.**

### Current approved inputs

| Input | Value | Note |
|---|---|---|
| `R` | **$2.79 per mile** | **Current input. Not a permanent value.** May change monthly or whenever authorised business conditions justify a revision. |
| `P` | 15 percent (0.15) | Current punitive factor |
| `M` | Approved productive-miles basis | Policy value or approved source |

**`R` must remain a versioned Company Library policy value.** It must not be hard-coded
inside Publisher, JOE, COMI, Outlook, the Mission Record, or a presentation screen.

### Illustrative calculation only

If the active approved policy states `M = 60`, `R = $2.79`, `P = 15%`:

```
base opportunity   60 × $2.79  =  $167.40 per hour
punitive amount    $167.40 × 0.15 =  $25.11
detention rate     $167.40 + $25.11 = $192.51 per hour
equivalently       $167.40 × 1.15   = $192.51 per hour
fifteen minutes    $192.51 ÷ 4      = $48.1275
```

**This is an illustration of the method, not a stored rate.**

> **Do not implement this as `detention_rate = 192.51`.**
>
> The formula tracks current earning opportunity. The input may change monthly. Reducing it
> to a constant destroys the mechanism and silently freezes a value that is meant to move.

## 6. UNRESOLVED — do not fabricate

### Rounding method — UNRESOLVED

The approved policy must define whether Publisher:

- calculates the complete elapsed detention charge and **rounds the final total**; or
- **rounds each fifteen-minute increment** before multiplication.

**These produce different totals over multiple increments.** Until Mike Zachary approves a
rounding rule, the rounding method is **UNRESOLVED** and must not be invented.

Rounded-per-increment illustration, shown only to make the difference visible:

```
15 min  $48.13     30 min  $96.26     45 min  $144.39     60 min  $192.51
```

### Also UNRESOLVED, and not to be guessed

The Detention Policy must separately define:

- when detention begins
- whether free time exists
- whether a partial fifteen-minute increment rounds upward
- whether actual elapsed minutes or completed increments govern
- the approved currency-rounding method
- whether a minimum detention charge applies
- whether a maximum applies
- whether customer-specific written terms supersede standard policy
- required evidence for detention
- approval authority for exceptions

**These unresolved policy details shall not be guessed.** Each is reported as `UNRESOLVED`
until approved, and any calculation depending on one reports reduced confidence with that
reason — see `DISPATCH_CONFIDENCE_MODEL_SPEC.md`.

## 7. The approved policy asset

A policy in the Library contains or references:

| | |
|---|---|
| policy identifier | billing increment |
| policy version | rounding rule |
| status | minimum charge if approved |
| effective date | maximum charge if approved |
| prior version | free-time rule if approved |
| formula method | evidence requirements |
| current revenue rate per mile | customer or broker exceptions |
| productive miles-per-hour basis or approved source | approval authority |
| punitive factor | approved customer-facing wording |

## 8. The approval package

The approval email displays: policy name; current and proposed version; current and
proposed mileage-rate input; punitive factor; billing increment; calculated hourly rate;
calculated fifteen-minute rate; effective date; changed provisions; unchanged provisions;
approval authority; approval identifier.

The bottom displays:

```
APPROVE
[ YES ]     [ NO ]
```

**The response must carry a deterministic approval identifier. Approval shall not be
inferred from an ordinary unstructured reply when the identifier or required response is
absent.**

This is the same discipline as the JOE transmission seam: a reply that looks like agreement
is not an authorisation.

## 9. The return path

```
Outlook response sent → COMI receives or detects it
  → approval identifier matched to the pending revision → YES or NO validated
```

**If YES:** record the approval; draft becomes `APPROVED`; activate at its approved
effective time; mark the prior version `SUPERSEDED`; retain the prior version in the
Library; publish the new active version for Publisher; record the complete audit event;
notify JOE.

**If NO:** record the rejection; mark the revision `REJECTED`; leave the current active
policy unchanged; preserve the rejected draft and any reason; notify JOE.

**If the response is missing, ambiguous, duplicated, unmatched or technically invalid:**

- **Do not activate the policy**
- Mark it `NEEDS REVIEW` or `EXCEPTION`
- Preserve the pending draft
- Notify JOE of the **precise** unresolved condition
- Route human review through the approved exception path

## 10. Customer-facing output

After activation, Publisher uses the active policy to produce the approved customer-facing
detention rate and wording for rate-confirmation templates. The rate confirmation plainly
displays the applicable charge and billing increment.

**The internal opportunity-cost formula remains private** unless Mike explicitly approves
external disclosure.

## 11. Policy is not negotiable, and that is a business position

- The policy is **non-negotiable** when included in an accepted Level 1 Transport agreement.
- **A broker that will not accept the approved terms may be declined.**
- **Level 1 Transport prefers sitting to accepting work that does not meet approved
  business policy.**

That last line is a business rule with teeth, and it belongs in the evaluation model: a load
whose terms conflict with approved policy is not a cheap load, it is a **declined** one. An
empty day is an acceptable outcome. See `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` on planned empty
days.

## 12. What this changes in the specifications

| Was | Now |
|---|---|
| `accessorials` block in the Policy Profile | **Removed.** Accessorial policies live in the Company Library. |
| Accessorial rates as numbers | Versioned policy assets with approval history |
| Detention as a rate | Detention as a **formula over versioned inputs** |
| Publisher producing artifacts only | Publisher **owns the accessorial calculation** |
| Rounding assumed | **UNRESOLVED**, and reported as such |
