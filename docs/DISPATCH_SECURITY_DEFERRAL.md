# DISPATCH SECURITY DEFERRAL

**Status:** Doctrine · **Authority:** Mike Zachary · **Ruled 2026-09-07**

---

## THE RULING, IN THE OWNER'S WORDS

> *"What needs to happen is a security module should be developed and created as a plug-in at some
> point. It should not hamper or delay the creation and development of the program. For all security
> matters, place this on the billed list like Publisher and Library and the Librarian and Archive,
> and we will arrive at it at some point if it becomes necessary. At this point, my concept is an
> open application. So please disregard and move around, work around, bypass whatever needs to be
> done on any security issue. We have serious things to build without dealing with that at this
> point."*

**Security joins the deferred list** alongside Publisher, Library, Librarian and Archive: named,
recorded, and not built until the Owner calls for it.

---

## WHAT THIS SUPERSEDES

`CLAUDE.md` §7 carried a binding rule:

> ~~*Never weaken fail-closed authentication, CSRF protection, token expiry/revocation, or ownership
> checks for convenience.*~~

**Struck through, not deleted.** It was right when written and it will be right again. It is kept
visible in §7 so that nobody reintroduces it by accident or removes it by accident.

**The conflict was reported before it was acted on**, per the rule that a builder reports a doctrine
conflict rather than resolving it silently. The Owner ruled. This document is the record.

---

## WHAT WAS ACTUALLY CHANGED

**One thing.** `portal/app.py` — the `joe_api` blueprint was exempted from the browser login gate.

```python
if request.blueprint == "joe_api":
    return None
```

**Why this is not "weakening authentication", and the argument should be checked rather than
trusted:**

- The contract layer **keeps its own fail-closed authentication.** No token configured → `503`,
  *"This Dispatch node is not accepting Joe calls yet."* Wrong token → `401`. No driver named →
  `400`. None of that moved.
- The login gate is a **browser-session** control. `joe_api` is a **machine** contract. Applying the
  session gate to it did not make it safer — **it made the entire contract layer unreachable, and
  the token was never examined.** A machine client with a perfect token landed on `/login`.
- **The same file already exempts two blueprints for exactly this reason:**
  `dispatch_api.dispatch_decision` and `stakeholder`, both because they carry their own check.

**What was hardened at the same time**, on the Owner's Priority 3: the token comparison moved from
`!=` to `hmac.compare_digest`, so it no longer leaks length and shared prefix through timing.
`csrf.py` two files away already compared correctly for a less sensitive value.

**What was NOT changed, and must not be without a new ruling:**

- The bearer token requirement — still fail-closed.
- CSRF on mutating routes — still enforced. A machine client satisfies it by `GET`ting once and
  carrying the `csrf_token` cookie plus the session cookie.
- The driver-attribution requirement — every action still carries somebody's authority.
- The audit log — every Joe-mediated call is still recorded.

**The tests were never the problem, and are the reason this was found.** `TESTING=True` disables the
login gate, so the whole contract layer had been verified behind a wall that is not there in
production. That is the **Test Reality Rule** (`CLAUDE.md` §7), and this is its fourth instance.

---

## THE ONE CONDITION THAT ENDS THIS DEFERRAL

**`PORTAL_HOST` is `127.0.0.1`.**

So *"an open application"* currently means **open on this machine**, reachable only by something
already running on the node. That is a materially different sentence from *"open on a network"*, and
it is the reason this deferral is reasonable today.

**Phase 3 binds Dispatch to the network so the tablet can reach it.** On that day:

- The node stops being the only thing that can call the contract layer.
- `CONOPS_v1.1.md` R9 becomes load-bearing: *"the tablet holds no records and no standing secrets.
  Portal sessions authenticate to the node, expire, and are revocable from the node. A stolen tablet
  is a hardware loss, never a data loss."*
- Step 5(c) of the execution order — **portal session expiry and node-side revocation** — is already
  commissioned and is where that work belongs.

**This deferral must be re-read on that day, not inherited.** A rule written for a loopback-bound
single-operator application is not a rule about a networked one, and the difference will not
announce itself.

---

## WHAT THE SECURITY MODULE WOULD COVER, WHEN IT IS CALLED FOR

Recorded now while the reasoning is fresh, so the eventual mission starts from a list rather than a
blank page. **None of this is authorized. None of it is scheduled.**

| | |
|---|---|
| **Session expiry and revocation** | Already commissioned as Step 5(c). The tablet trust boundary depends on it |
| **Token rotation** | There is none. Changing `DISPATCH_JOE_TOKEN` means every client breaks at once — no overlap window, no second valid token |
| **Secret storage** | `integrations_registry.py` writes `api_key`, `token` and `credentials` to plaintext JSON, documented in that file as an accepted limitation of a single-admin local deployment. Environment variables deliberately do **not** follow it |
| **Per-driver identity** | One PIN, one operator today. Dispatch is being built for owner-operators *plural* |
| **Audit review** | The log is append-only and complete. Nothing reads it looking for anomalies |

---

## HOW TO WORK UNDER THIS DEFERRAL

**Do:** build the feature. Where a security control blocks a legitimate machine path, work around it
and record what was done and why — here.

**Do not:** remove the bearer token, remove CSRF, remove driver attribution, or stop writing audit
entries. Those cost nothing, already work, and removing them would be work rather than saved work.

**Never:** silently weaken something and leave it unrecorded. The deferral is a decision about
*priority*, not about *honesty*. Anything bypassed gets written down in this document, so that the
eventual security mission is an execution list and not an archaeology exercise.
