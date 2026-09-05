# Dispatch — Connector Provider Insertion

**Written by:** Claude Code (implementation engineer) · 2026-08-24
**Applies to:** `dispatch/connectors/` · Operational Readiness Mission Section 6

This document answers one question for each of Dispatch's eight connectors: **what has
to happen before it talks to something real, and who decides.**

Two statements of fact, as of this writing:

- **No connector in Dispatch is connected to an external system.** Seven of the eight
  report `UNCONFIGURED`. The eighth, the Email Transport Connector, reports `SIMULATED`
  when no SMTP relay is set — meaning messages are written to `Archive/Outbox` as `.eml`
  files and delivered to nobody — or `CONFIGURED` when a relay is set but no message has
  been accepted yet.
- **Nothing in this document authorizes an activation.** Every provider choice, every
  credential, and every first live exchange is Mike's decision. Code that is written,
  reviewed and tested is `UNVERIFIED` until it has been proven on Mike's machine.

---

## 1. The vocabulary, before anything else

Every connector answers with one of these eight words and no others. They are defined in
`dispatch/connectors/contract.py::ConnectorStatus` and mirror mission Section 1.8.

| Word | Means |
|---|---|
| `LIVE` | Actual communication with the real external system occurred **and is evidenced** |
| `CONFIGURED` | Credentials/endpoints present and validated; no live exchange evidenced yet |
| `UNCONFIGURED` | Required configuration absent |
| `SIMULATED` | A mock or stand-in produced the data |
| `UNAVAILABLE` | Configured, but the last attempt failed |
| `MANUAL` | A human performed the step outside Dispatch and recorded it |
| `ABSENT` | The step was not performed at all |
| `UNVERIFIED` | Implemented in code but not proven on Mike's machine |

Words that are **not** available, and are refused by name if anyone reaches for them:
`CONNECTED`, `VERIFIED`, `CURRENT`, `ONLINE`, `ACTIVE`, `OK`, `HEALTHY`, `READY`.

`LIVE` cannot be produced by setting a field. `Provenance` refuses to be constructed with
`status=LIVE` unless it carries `ExchangeEvidence` — an endpoint that answered, a
SHA-256 fingerprint of the response, and the time the exchange completed. Those are
artifacts only a real round trip produces.

---

## 2. What a connector may never do

From Section 6.2, and enforced rather than requested:

> Connectors transport and normalize information. They do **not** own lifecycle
> transitions, human decisions, pricing authority, acceptance authority, scheduling
> truth, or operational doctrine.

The chain stays: Intelligence acquires → Intelligence Analyst reasons → Route Risk
evaluates mission consequence → COMI routes communications → Publisher produces approved
communications → Spine owns lifecycle truth → **Mike decides**.

Three mechanisms hold that in place, and a provider insertion must not weaken any of
them:

1. **`CapabilityDeclaration` refuses the words.** A connector cannot declare "approve",
   "accept", "set pricing", "scheduling truth" or "doctrine" as a capability — the
   dataclass raises at construction.
2. **The import graph is scanned.** `dispatch/connectors/boundary.py::verify_package`
   parses every file in the package and refuses any import of `dispatch.spine`,
   `dispatch.services` or `dispatch.store` (directly or transitively), any import of
   `sqlite3`/`dispatch.db` outside `audit.py` and `boundary.py`, and any SQL naming a
   table other than `connector_audit`. `tests/test_connector_boundary.py` runs it.
3. **The runtime seal.** `boundary.execute()` runs `fetch()` with `sqlite3.connect`
   replaced by a guard, so any database access from inside a connector call raises
   `BoundaryViolation`. A provider SDK that opens its own connection is caught even
   though no import scan could have seen it.

A connector returns a `NormalizedPayload`. Something with authority — Spine, COMI, or a
person — decides what to do about it.

---

## 3. The insertion procedure (every connector, same six steps)

**Step 1 — Mike selects the provider.** A named vendor, a named plan, and a named
account. Recorded in `DECISION_LOG.md`. Nothing starts before this.

**Step 2 — Configuration keys are set in the environment, and nowhere else.** Each
connector's `required_config_keys` are read from `os.environ` at the moment they are
asked. Connectors do not read credentials from the database or from a JSON file this
application can write: a connector that could configure itself could also silently
reconfigure itself.

> The Settings page's **System Keys** card (`portal/models/integrations_registry.py`)
> stores integration credentials in plaintext JSON for a future wiring, and is **not**
> read by any connector today. Wiring it to connectors is its own decision, and it needs
> encryption-at-rest answered first — see that module's security note.

**Step 3 — Implement `fetch()` and the normalizer.** Subclass behaviour only; the
identity, capability, configuration, authentication, health, audit and refusal paths
already exist in `BaseConnector`. The normalizer maps the provider's vocabulary onto the
connector's fixed payload shape, so a second provider never reaches the consumers.

**Step 4 — Return evidence, or do not claim `LIVE`.** Build `ExchangeEvidence` from the
actual response (`ExchangeEvidence.from_response(endpoint, response_bytes)`). If there is
no response, the honest status is `CONFIGURED`, `UNAVAILABLE` or `SIMULATED`.

**Step 5 — Prove it with tests before it is switched on.** Configuration validation,
authentication failure, timeout with retry, malformed payload, secret redaction, and the
audit row for each. The mock (`dispatch/connectors/mock.py`) is the model.

**Step 6 — Mike authorizes the first live exchange.** Steps 1–5 produce an `UNVERIFIED`
connector. It becomes proven when Mike runs it on his own machine and a real exchange is
recorded in `connector_audit` with a real evidence fingerprint. **No test run, on any
machine, is that proof.**

---

## 4. The eight connectors

### 4.1 Route Risk Connector — `route_risk`

| | |
|---|---|
| Status today | `UNCONFIGURED` |
| Config keys | `DISPATCH_ROUTE_RISK_API_URL`, `DISPATCH_ROUTE_RISK_API_KEY` |
| Collects | weather · traffic · DOT restrictions · law-enforcement conditions · port conditions · disaster conditions · fuel conditions · security conditions · road restrictions · mission advisories |
| Never | Accepts or cancels a load. Changes Current Reality without a governed Spine event or human authority. |

Route Risk is an **Operational Intelligence function, not a weather feed**. The connector
collects conditions; the **evaluation layer** (`AdvisoryRouteRiskEvaluator`, same module,
separate object) turns them into findings, consequence levels (0–5), COMI notification
requirements, Mission Visibility update requirements, stakeholder communication inputs
and map-visual requirements. A provider insertion touches the collection half only.

Existing internal Route Risk recording (`dispatch/route_risk.py`, `route_risk/engine.py`)
is unaffected and stays labelled as internal/manual.
`assessment_to_event_kwargs()` hands a finding to that existing engine in the shape it
already accepts, carrying the status word into the stored summary text.

**Mike decides:** which provider (NOAA/NWS is free and public; commercial traffic and
truck-restriction data is not), and whether a consequence level ≥ 3 may trigger a
stakeholder communication automatically or must wait for him.

### 4.2 Accounting Connector — `accounting`

| | |
|---|---|
| Status today | `UNCONFIGURED` for any live posting; `MANUAL` for the export that exists |
| Config keys | `DISPATCH_ACCOUNTING_API_URL`, `DISPATCH_ACCOUNTING_API_KEY` |
| Wraps | `dispatch/accounting_export.py` — one JSON file per settlement, written locally |
| Never | Writes a settlement, invoice or payment into Dispatch. Decides what is owed. |

The local export is a real, completed step performed **outside** Dispatch by a person, so
it reports `MANUAL` with the file path as its source reference — not `UNCONFIGURED`
(which would hide a step that happened) and not `LIVE` (nothing was contacted).

**Mike decides:** QuickBooks Online vs Desktop vs a CSV a bookkeeper imports; what
triggers an export (per invoice, per payment, or a batch); and — separately — whether
Dispatch may ever *read* payment status back, which is a reconciliation input and still
not a replacement for Dispatch's own settlement record.

### 4.3 Scanner Connector — `scanner`

| | |
|---|---|
| Status today | `UNCONFIGURED` |
| Config keys | `DISPATCH_SCANNER_API_URL`, `DISPATCH_SCANNER_API_KEY` |
| Collects | scanned document artifacts · page counts and checksums · OCR readings with confidence |
| Never | Creates an evidence record. Attaches a document to a load. |

A scanned document is a **candidate** until a person attaches it. Evidence records, and
the `uploaded_by` identity on them, are written by `dispatch/services.py::attach_evidence`
and nowhere else. An OCR reading travels with its confidence, following the
`ifta_fuel_purchases.extraction_confidence` precedent.

**Mike decides:** the device or service, and whether an OCR reading may ever pre-fill a
field a human then confirms (the existing receipt-vision pattern) or must stay
display-only.

### 4.4 Outlook Connector — `outlook`

| | |
|---|---|
| Status today | `UNCONFIGURED` |
| Config keys | `DISPATCH_OUTLOOK_TENANT_ID`, `DISPATCH_OUTLOOK_CLIENT_ID`, `DISPATCH_OUTLOOK_CLIENT_SECRET` |
| Collects | calendar events as Outlook holds them · free/busy windows · Outlook-derived capacity |
| Requires human authorization | `request_event_creation` |
| Never | Keeps a second calendar. Writes scheduling truth into Dispatch. Creates an event unasked. |

**Outlook is the single source of scheduling truth.** Dispatch may evaluate fit, present
schedule information, show Outlook-derived capacity, and request event creation *after*
human authorization. It may not create a second scheduling truth — which is why there is
no `sync` operation, no local calendar table, and no code path writing a schedule into
Current Reality.

`request_event_creation` refuses without an `authorized_by` identity **and** an
`authorization_reference` pointing at a decision recorded elsewhere. It refuses reserved
system identities. It will never manufacture an approval attribution to Mike. This gate
is checked *before* configuration, so it is exercised by test today rather than running
for the first time in production.

**Mike decides:** the Microsoft 365 app registration and its consent; which calendar;
and whether Dispatch may request event creation at all, or only display.

### 4.5 Email Transport Connector — `email_transport`

| | |
|---|---|
| Status today | `SIMULATED` with no relay set; `CONFIGURED` with one; `LIVE` per accepted message |
| Config keys | `DISPATCH_SMTP_HOST` (+ `_PORT`, `_USER`, `_PASSWORD`, `_STARTTLS`) |
| Wraps | `cin_lite/email_delivery.py` — the program's **sole** mail transport, unchanged |
| Never | Decides what may be sent. Bypasses COMI routing or the Publisher. |

The wrapper adds only the status word, by classifying the receipt the transport already
returns:

| Receipt | Status |
|---|---|
| `sent via <host> to <addrs>` | `LIVE`, with the receipt fingerprinted as evidence |
| `not sent (SMTP not configured); written to <path>` | `SIMULATED` — **delivered to nobody** |
| `delivery failed (<exc>); written to <path>` | `UNAVAILABLE`, exception text redacted |
| anything else | `UNAVAILABLE` / `malformed_payload` — delivery is *unknown*, never assumed |

No retry is added here: the transport already falls back to a file, so a retry at this
layer would duplicate an `.eml` or, on an intermittent relay, a delivery.

**Mike decides:** the relay (SendGrid, SES, Mailgun, Postmark, the domain's own SMTP),
the sending domain and its SPF/DKIM records, and whether unattended sending is permitted
at all.

### 4.6 Load Board Connector — `load_board`

| | |
|---|---|
| Status today | `UNCONFIGURED` for `fetch_loads`; `SIMULATED` for `sample_loads` |
| Config keys | `DISPATCH_LOAD_API_URL`, `DISPATCH_LOAD_API_KEY` |
| Wraps | `dispatch/acquisition.py` — the existing load-shape normalizer |
| Never | Books a load. Treats a posted rate as an agreed one. |

`fetch_loads` **refuses** rather than falling back to the local sample directory the way
`acquisition.acquire()` does. That fallback is right for a development script and wrong
for an operational boundary: sample records presented after a provider outage would be
fiction shown as a market. `sample_loads` returns the same records deliberately, labelled
`SIMULATED`, with "none of them can be booked" in the payload.

An offer is a candidate: Opportunity scores it, Spine records the work item, and a human
answers at the `WAITING_FOR_MIKE` gate.

**Mike decides:** DAT vs TruckSmart vs another board (both are named, neither connected,
in the Settings System Keys card), the subscription, and the search filters that define
what Dispatch even sees.

### 4.7 Mapping and Routing Connector — `mapping`

| | |
|---|---|
| Status today | `UNCONFIGURED` |
| Config keys | `DISPATCH_MAPPING_API_URL`, `DISPATCH_MAPPING_API_KEY` |
| Collects | route geometry · practical and truck-legal distances · drive time estimates · map visual references |
| Never | Sets a rate from a mileage. Writes a distance into a load record. |

Every distance carries the provider that produced it and the profile it was computed
under (`practical`, `shortest`, `truck_legal`) — the difference between "the broker posted
350 miles" and "372 practical truck miles" is real and shows up in a settlement. A
distance with no provenance is not upgraded by passing through here.

**Mike decides:** the provider (PC*MILER and Trimble are the industry standards and are
paid; free routing engines are not truck-legal), and whether a computed mileage may ever
replace a posted one on a load record — which is a Current Reality write and therefore
not the connector's to make.

### 4.8 Future External Intelligence Connector — `future_intelligence`

| | |
|---|---|
| Status today | `UNCONFIGURED` |
| Config keys | none — there is no provider |
| Declares | **no capabilities** |
| Never | Becomes a source of unlabelled operational truth. |

The registered slot for external intelligence Dispatch has not chosen: market rate
indices, broker credit and days-to-pay, carrier authority and safety records, fuel price
feeds, freight demand signals. It exists so the first such source is built *behind* the
contract instead of beside it.

Anything it eventually produces is a **Possible Future**: advisory, labelled, and never a
silent mutation of Current Reality.

**Mike decides:** whether any of it is worth paying for, and what a number from it is
allowed to influence.

---

## 5. The audit trail

Every connector attempt writes one row to `connector_audit` — including the attempts that
never left the building. The schema is installed by
`dispatch/connectors/audit.py::init_connector_schema`, called from
`dispatch/db.py::_init_db` beside the Spine and token initializers.

| Column | |
|---|---|
| `connector_id`, `provider`, `operation` | who was asked, and for what |
| `status` | the truth word |
| `outcome` | `ok` · `refused` (Dispatch declined to try) · `failed` (attempted, no answer) |
| `reason` | the labeled refusal sentence, **secrets redacted at construction** |
| `attempts` | how many tries were spent |
| `evidence_fingerprint` | the SHA-256 of the response, on a `LIVE` row |

"The accounting connector was asked for a settlement export at 14:02 and refused because
it is `UNCONFIGURED`" is the sentence this table exists to produce. A blank field beside
an empty table is indistinguishable from a provider that answered with nothing.

---

## 6. Displaying connector data

Any consumer displaying connector data **must** display the status. A `SIMULATED` or
`UNAVAILABLE` payload must never render as operational intelligence without that label.

- Render through `NormalizedPayload.to_display_dict()`, which puts `connector_status` and
  `connector_label` in the same mapping as the values, so a template iterating the dict
  cannot show the numbers and miss the label.
- Call `assert_labeled_display(rendered)` on anything handed to a template. It runs in
  production, it is cheap, and it turns "we remembered the label" into a failure when
  somebody does not.
- `registry.status_board()` is the sanctioned source for a connector inventory screen;
  every row carries a truth word for the connector, its configuration, its authentication
  and its health.

---

## 7. Mike-only decisions, collected

Nothing below may be decided by code, by a default, or by an implementation engineer.

1. **Provider selection** for each of the eight — vendor, plan, account.
2. **Credential issuance and entry** — no credential is generated, stored or defaulted by
   Dispatch.
3. **Authorization of the first live exchange** for each connector. Until then the
   connector is `UNVERIFIED`, whatever the test suite says.
4. **Whether Route Risk findings may trigger stakeholder communication** without him.
5. **Whether Outlook event creation is permitted at all**, or Outlook stays read-only.
6. **Whether unattended email sending is permitted**, and from which domain.
7. **Whether accounting data may be read back** into Dispatch, and what it may touch.
8. **Whether a computed mileage may replace a posted one** on a load record.
9. **Whether the System Keys registry is wired to connectors**, given it stores secrets in
   plaintext today.
10. **Deactivating a connector** — removing configuration is an operational act with the
    same weight as adding it.
