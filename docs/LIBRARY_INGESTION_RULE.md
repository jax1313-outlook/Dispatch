# LIBRARY_INGESTION_RULE.md

**Document Type:** Library Ingestion Doctrine
**Program:** Dispatch
**Owner:** Mike Zachary / Level 1 Transport
**Status:** Current Doctrine — Amends Library Governance in `DISPATCH_FINAL_BLUEPRINT_v1.md` §8
**Authority:** Mike Zachary remains final authority

---

## 1. Purpose

This rule defines how material enters any Dispatch Library. It corrects and supersedes any prior blueprint language that implied a verification/approval/promotion gate applies to documents a human places directly into Library. It does not change Publisher's existing review/approval process, and it does not weaken the No Fabrication Rule for AI-authored or AI-interpreted content.

---

## 2. Core Rule

**Any document placed into any Library by a human is accepted immediately.**

- No verification workflow.
- No approval workflow.
- No promotion workflow.

A human placing a document into Library is itself the approval act. The human's deliberate selection and placement of a specific document into a specific Library section is an authoritative human decision. Requiring an additional verification/approval/promotion layer on top of it would be redundant gating of an action a human already authorized directly — not a safeguard.

---

## 3. Scope — What This Rule Covers

This rule applies only to documents/records a human directly places into Library (for example: uploading a rate sheet, a signed template, a compliance document, a company policy, or a scanned form).

It does **not** apply to:

- **Publisher-generated assets** — drafted, assembled, or compiled by the Publisher cognitive function. These continue to require Publisher's existing review/approval process (`PUBLISHER.md` §9, §14) before any Library entry.
- **Intelligence-nominated candidates** — Intelligence may still nominate findings for Library review; that nomination path is unaffected. This rule does not create an automatic promotion path for Intelligence output (`INTELLIGENCE_ANALYST.md` §12 unaffected).
- **Archive-nominated historical records** — Archive material still requires the existing Library promotion workflow before becoming Library truth (`ARCHIVE_REVIEW_POLICY.md` §8 unaffected).

---

## 4. Why This Does Not Violate the No Fabrication Rule

The No Fabrication Rule (`DISPATCH_CONSTITUTION_v3.md` §10) exists to stop the system from inventing facts or treating AI/cognitive output as truth without traceability. A human directly placing a real document into Library is not an act of fabrication — the document is the source, not an inference about the document. The verification/approval/promotion gate that `DISPATCH_FINAL_BLUEPRINT_v1.md` §8.3–8.4 and `INTELLIGENCE_VERIFICATION_WORKFLOW.md` describe governs facts derived, extracted, or drafted by cognitive functions — not documents a human hands the system directly.

---

## 5. Publisher-Generated Assets Are Unaffected

Publisher continues to draft only, never approve (`PUBLISHER.md` §16). Any Publisher output nominated for Library — reusable packet language, templates, approved facts distilled from a draft — still requires Mike's review through Portal or the approved Library promotion workflow (`DISPATCH_FINAL_BLUEPRINT_v1.md` §8.3) before it enters Library as truth. This rule does not create a bypass for Publisher output routed through a human's hands without genuine human review of that specific content.

---

## 6. Security Sub-Library

Library includes a distinct **Security sub-library** for security-sensitive material — PIN policy documents, credential-handling procedures, access-control records, and other material `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` governs.

- **PIN-protected access** — opening the Security sub-library requires a separate, valid PIN check at the moment of access, distinct from the general Portal session login PIN (Security Spec §4.3). An already-logged-in Authority user must re-authenticate with a PIN to open the Security sub-library.
- **PIN reset capability** — an Authority user may reset the Security sub-library's access PIN through the same governed PIN reset workflow already defined in the Security Specification (§4.5) — Authority approval or an approved reset workflow, never a silent reset.
- Governed by Security Spec §11 (Library and PIN Records): the Security sub-library may store PIN-related and credential-control records, but must never expose readable PIN values to Publisher, Intelligence, Driver users, External Viewers, or any cognitive function. Publisher may not use Security sub-library records. Intelligence may not interpret them.
- The Human Ingestion Rule (Section 2) still governs *what* enters the Security sub-library — a human placing a document there is accepted immediately. The PIN-protected access requirement governs *who may reach it*. These are independent controls; one is not a substitute for the other.

---

## 7. Scanner API Integration — Future Build Item

A Scanner API integration (physical/network document scanner intake feeding directly into Library ingestion) is identified as a **future build item**, not authorized for implementation now. It is recorded here so the Library ingestion path is designed to accept a scanner-originated document the same way it accepts any other human-placed document, once built. No scanner vendor, protocol, or implementation detail is specified or authorized by this doctrine. Priority: Future.

---

## 8. Relationship to Version Doctrine

Human-placed Library documents still receive `Ver: X` / `Last Change:` display per `DISPATCH_VERSION_DOCTRINE.md`. Immediate acceptance does not exempt a record from version tracking — a new upload of a revised document is a new version, not a silent overwrite.

---

## 9. Relationship to Archive

If a human-placed Library document is later superseded, the prior version follows the existing Archive Review Policy retention rule (Current Version + Three Previous Versions) exactly as any other Library asset. Immediate acceptance on ingestion does not change retention/versioning doctrine on the back end.

---

## 10. Success Standard

This rule succeeds when a human can place a real document into Library and have it usable immediately, without waiting on a review cycle that adds no safety value for content a human already vouched for by placing it — while Publisher-generated and cognitively-derived material continues to pass through the review/approval and verification gates those functions require.

---

## 11. Authority Closing

This rule does not authorize AI-originated content to bypass verification.
This rule does not authorize Publisher to self-approve.
This rule does not weaken the No Fabrication Rule.

Mike decides.
