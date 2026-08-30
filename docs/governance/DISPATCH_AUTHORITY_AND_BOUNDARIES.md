# Dispatch — Authority and Boundaries

**Program:** Dispatch · **Final authority:** Mike Zachary
**Status:** binding · current as of 2026-08-25

This document answers one question: **who is allowed to decide what.** Everything else in
the repository — the architecture, the truth vocabulary, the proof procedures, the refusal
paths — exists to keep the answer below true in practice.

---

## 1. The authority rule

> **Mike Zachary is the final authority. Software, automation and AI hold zero decision
> authority.**

Dispatch provides **information, analysis, and recommendations**. The human retains
**acceptance, rejection, priority, override, commitment, and business decisions**
(Driver-First D10).

This is not a preference about tone. It is a constraint on what code may do.

### 1.1 Dispatch shall not silently assume authority

A system assumes authority silently in four ways, all forbidden:

| How it happens | What it looks like in code |
|---|---|
| **Defaulting** | An approval field with a default of "approved" |
| **Inferring** | Treating "he looked at it" as "he accepted it" |
| **Auto-advancing** | A state machine that moves past a human gate when nothing was clicked |
| **Presenting a recommendation as a decision** | A card that says "Rejected" when it means "scored low" |

### 1.2 Score does not decide

Scoring exists to **reduce noise and sort human attention**. It does not approve, reject,
or choose. A score may change the order of a list and may raise a warning. It may never
remove an option from Mike's view without saying it did, and it may never commit anything.

Route Risk, capacity analysis, opportunity scoring and every connector are in this
category: they **advise**. The Spine decides state; Mike decides business.

### 1.3 Recommendations are labelled

Every recommendation carries the fact that it is one. The Spine's decision-support object
carries a fixed closing string, enforced in `dispatch/spine/models.py`:

> `"This is a recommendation only. No action is authorized. Mike decides."`

Do not soften it, do not make it conditional, and do not omit it because the surface looks
cluttered.

---

### 1.4 The one thing a score is allowed to send

**This is an exception to 1.2, and it is the only one.** It is written down
because an undocumented exception becomes a precedent, and the next one gets
added by analogy to this one rather than by decision.

When a load scores highly enough, Dispatch sends a fixed template email to the
broker or shipper who posted it. Owner's description of what that email is:

> "it is nothing more than hey, hello call me"

Its whole purpose is to put Level 1 Transport's name, company and contact
details at the top of a pile that is worked in the order it arrives. Freight
goes to whoever answers first, and by the time a human has read the card the
pile has moved.

**Why it does not break 1.2.** The email approves nothing, rejects nothing, and
chooses nothing. It commits Level 1 Transport to no rate, no lane, no date and
no equipment. It removes no option from Mike's view and changes none of them.
It says the carrier is interested and here is how to reach him — the same thing
a phone call would say, sent faster.

**What holds it to that.** All of these, or it is no longer this exception:

1. **Fixed template.** The wording is not generated per load. Anything that
   composes a fresh message per opportunity is a different capability and needs
   its own decision.
2. **No number in it.** No rate, no rate per mile, no commitment to a window.
   A template that acquires a figure stops being an expression of interest and
   becomes an offer.
3. **No acceptance language.** Not "we'll take it", not "booked", not
   "confirmed". 1.3 and the attribution rule in section 2 apply in full.
4. **The card still asks.** The load is presented to Mike as a card requiring a
   decision, exactly as it would have been if nothing had been sent. The email
   does not advance the load through workflow.
5. **Visible after the fact.** The card carries an Email Sent banner. Mike can
   always see that Dispatch spoke on his behalf, and what it said.
6. **Score sets the trigger, and nothing else.** The score decides *whether the
   template goes*, and has no influence on its content. It is still not
   deciding the load.

**What this exception is not.** It is not a general licence for Dispatch to
send. It covers one fixed template, to the poster of a specific load
announcement, saying only that the carrier is interested. Every other outbound
communication remains Mike's, and JOE — which cannot send at all under Article
II of its own constitution — is unaffected by this entirely.

---

## 2. The attribution rule

> **Never manufacture, infer, default, auto-populate, seed, or test-fixture any of the
> following:**
>
> - *Verified by Mike Zachary*
> - *Approved by Mike Zachary*
> - *Accepted by Mike Zachary*
> - *Authorized by Mike Zachary*
> - *Confirmed by Mike Zachary*

A record may carry one of these **only** when Mike personally performed an authenticated
action that produced it.

This rule has no exceptions for convenience:

- Not in a **test fixture**. A fixture that writes "Approved by Mike Zachary" teaches the
  codebase that the string is available, and the next author reaches for it.
- Not as a **default** in a dataclass, a schema, or a form.
- Not as a **seed** in demo or sample data.
- Not by **inference** from a session, a click-through, or a timestamp.
- Not in a **document generated by a builder**, including mission reports. A report may say
  what a builder recommends; it may never say what Mike approved.

`RESERVED_SYSTEM_IDENTITIES` in `dispatch/rehearsal.py` keeps system actors
(`PUBLISHER`, `SYSTEM`, `AUTOMATION`, `INTELLIGENCE`, `LIBRARY`) from being used as a human
actor. `--actor` on the proof tooling is **never defaulted and never inferred**.

### 2.1 A backup is never "valid"

Dispatch will not call a backup valid. The states are `UNCONFIGURED` → `ABSENT` →
`UNVERIFIED` → `VERIFIED`, and only a **real restore that a human performed and recorded**
in `restore-verification.json` produces `VERIFIED`. No part of Dispatch writes that file
automatically. See `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md`.

---

## 3. Boundaries — what software may never do

### 3.1 Never weaken a refusal for convenience

The following are fail-closed and stay fail-closed:

- **Authentication.** The portal's `DISPATCH_PIN` Authority session gate
  (`governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md`) and the separate driver PIN
  registry. Failure closes; it does not fall through.
- **CSRF protection** on every mutating route.
- **Token expiry and revocation.** `dispatch/tokens.py` — HMAC-SHA256 signed, with `issue`,
  `verify`, `revoke`, `revoke_for_object`, and an audit trail. A token that cannot be
  verified is refused, not accepted with a warning.
- **Ownership checks.** `_verify_driver_load()` and its equivalents. A driver sees their own
  loads; that is enforced server-side, never by hiding a link.
- **Evidence integrity.** Extension allowlist, size cap, SHA-256 checksum on every attachment.

If one of these is inconvenient during development, use the documented development mode.
Do not edit the check.

### 3.2 Never fail silently

A refusal the operator cannot see is worse than a crash, because the crash gets fixed. Any
refused transition, rejected upload, or expired token must reach the surface that asked for
it. See `CLAUDE.md` §3 for the shipped defect this rule comes from.

### 3.3 Never claim more than the evidence supports

Never represent:

- **sample data as live data**
- **a requested action as a completed action**
- **an interface definition as a working integration**
- **test success as operational deployment proof**
- **a push as having occurred** unless it was verified

Use the eight truth words (`CLAUDE.md` §6). Do not invent a ninth.

### 3.4 Never commit

Runtime secrets · logs containing secrets · rehearsal databases · evidence files · backups ·
anything under `proof/`. The launcher redacts secret **values** and prints secret **names**;
`.gitignore` covers the rest. Both are load-bearing.

### 3.5 Never restore a backup into the live store

A restore goes to a separate location and is inspected there. Restoring over live data
destroys the thing you were trying to protect if the archive turns out to be bad.

---

## 4. Plug-in boundaries

Route Risk, Mission Visibility, SAM and Assistant are **plug-ins**.

| Rule | |
|---|---|
| **Startup** | Dispatch starts and runs core operation with every plug-in absent |
| **Embedding** | Assistant code is not embedded into Dispatch; Dispatch is not redesigned around Assistant |
| **Write authority** | **No direct Dispatch write authority may be granted to Assistant.** A plug-in proposes through the connector boundary; Dispatch's own code performs any write |
| **Entry** | Every external system enters through `dispatch/connectors/` and nowhere else |
| **Failure** | **Degradation is permitted. Incapacity is not.** An absent plug-in yields `UNCONFIGURED` / `UNAVAILABLE` on a surface. It never prevents startup |

Guarded by `tests/test_repository_doctrine.py`.

### 4.1 There is no Manager component

**There is no Manager component in the current architecture. Do not create, restore,
reference, or infer a Manager component, Manager agent, or Manager authority.**

`docs/MANAGER.md` records a capability that was named in planning and never built. It
authorizes no code, no route, no data model and no runtime behaviour. One legacy state
string, `ROUTED_TO_MANAGER`, remains in the Spine's state list — recorded as an open
conflict in `docs/architecture/DISPATCH_ARCHITECTURE.md` §7.1, awaiting Mike's decision, and
deliberately not changed by a builder.

---

## 5. Doctrine authority

### 5.1 The repository is the source of truth

Not conversation history. A previous session's chat is gone and was never authoritative. If
a rule matters, it is written down here, in `CLAUDE.md`, or in `DECISION_LOG.md`.

### 5.2 Order of precedence

1. `DECISION_LOG.md` — a dated decision beats everything else
2. `CLAUDE.md`, this document, `DISPATCH_PURPOSE_STATEMENT.md`, `DRIVER_FIRST_DOCTRINE_v2.md`
3. `docs/architecture/DISPATCH_ARCHITECTURE.md` and the subsystem architecture notes
4. Reports, audits and matrices — **history, not instructions**

### 5.3 Changing doctrine

- Do not document unapproved ideas as doctrine. A builder's recommendation is labelled as one.
- Do not overwrite settled doctrine merely to match the current implementation. **If code
  conflicts with doctrine, report the conflict** — in the mission report and in
  `docs/architecture/DISPATCH_ARCHITECTURE.md` §7.
- **Do not edit old decisions to hide their history.** Mark them `SUPERSEDED` and cite the
  ruling that replaced them. A decision log that has been tidied is a decision log nobody
  can trust.

### 5.4 What a builder may decide alone

| A builder decides | Mike decides |
|---|---|
| Implementation approach within settled doctrine | Anything that changes doctrine |
| Naming, structure, and factoring inside a subsystem | Anything crossing a subsystem boundary (THE MIKE RULE) |
| Fixing a defect against a stated requirement | Whether a requirement is right |
| Adding tests | Removing, skipping or weakening one — **never permitted** |
| Recording a conflict | Resolving a conflict that touches persisted data or the data model |
| Writing a recommendation | Accepting it |
