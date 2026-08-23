# DISPATCH_SECURITY_AND_RUNTIME_REPORT

**Phases 5 and 9 — data/persistence audit and security/operational-safety audit**
**Audit commit:** `37f4fd033e57c55f46dfd0568d3371e8473d683f`
**No security architecture was changed by this mission.**

---

## PART A — Data and persistence (Phase 5)

### A.1 Where Dispatch stores things

| Store | Mechanism | Location | Durable |
|---|---|---|---|
| Freight engine | **SQLite**, 26 tables, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` | `PORTAL_DATA_DIR/dispatch.db`, else `DISPATCH_OPERATIONS_ROOT/Current Workspace/PortalData/`, else `portal/data/dispatch.db` (`dispatch/db.py:413-424`) | **Yes** |
| Portal models (11) | JSON files, written through `atomic_write_json()` — mkstemp in the same directory, `flush`, `os.fsync`, `os.replace` (`portal/models/__init__.py`) | Same data dir | **Yes** |
| Evidence uploads | Files named `{evidence_id}.{ext}` | `PORTAL_UPLOAD_DIR`, else `DISPATCH_MEMORY_ROOT/Evidence`, else `<data dir>/uploads` | **Yes** |
| Contract archive | Files plus `.sha256` sidecars, fail-closed verification on read (`cin_lite/archive.py:119-134`) | `DISPATCH_ARCHIVE_ROOT/CIN/…` | **Yes** |
| Email outbox | `.eml` files when SMTP is unconfigured | `Archive/Outbox` | **Yes**, but the filename is deterministic and **overwrites** |
| Route Risk events | SQLite `route_risk_events` since M3 | With the DB | **Yes** |
| **Route Risk events, standalone mode** | Module-level dict `_ROUTE_RISK_EVENTS` (`route_risk/engine.py:16`) | Process memory | **No** — Dispatch injects a `store_fn` so this path is not used in-app |
| Sessions | Flask signed cookie | Browser | Survives refresh, not a secret-key change |

### A.2 Survival matrix

| Event | Survives | Evidence |
|---|---|---|
| Page refresh | **YES** | Nothing is client-side state |
| Application restart | **YES** for SQLite and the JSON stores | `tests/test_route_risk_durability.py` proves this across a genuine two-process restart |
| Machine restart | **YES**, same mechanism | |
| Version upgrade | **PARTIAL** | `_apply_migrations()` runs guarded, idempotent `ALTER TABLE`s. There is **no schema version number and no down-migration.** A column removal or type change has no defined path. |
| Branch change | **YES** — `portal/data/` is gitignored, so checking out another branch does not touch the data | `.gitignore:19` |
| Deployment | **UNPROVEN** | No backup procedure, no export/import, no restore test exists anywhere in the repository |

### A.3 What is actually in this workspace

**There is no `dispatch.db` anywhere in this workspace.** `find / -name "dispatch.db"` returns only
pytest temporaries. The freight engine has never held an operational record here.

The six JSON files that do exist under `portal/data/` (≈336 KB) are entirely test and probe residue,
including 402 conflict notices. **They are test data, and if copied to Mike's machine they would
appear as operations.**

### A.4 Data findings

| # | Finding | Severity |
|---|---|---|
| D-1 | **No backup, no restore, no export.** The SQLite file plus eleven JSON files are the entire operational record, are deliberately untracked, and have no documented copy-out or copy-in procedure. A disk failure loses the business. | **BLOCKER for operational use** |
| D-2 | **No schema version and no down-migration.** Upgrades are forward-only and unlabelled. | HIGH |
| D-3 | **Sample data is the default acquisition source.** With `DISPATCH_LOAD_SOURCE` unset, `dispatch/acquisition.py:47` serves two tracked sample loads. Nothing marks them as samples once inside the system. | HIGH |
| D-4 | **Test residue is indistinguishable from operations** in `portal/data/`. | MEDIUM |
| D-5 | **The email outbox overwrites.** Two real sends to a deterministic filename leave one file — which is why C4's acceptance criteria require asserting on a ledger, never on the outbox. | MEDIUM |
| D-6 | **No retention policy is implemented.** The `retention` table exists; nothing can lawfully purge anything, including the 402 stale conflict notices. | MEDIUM |
| D-7 | **Load status is stored twice** — `loads.status` and `sandbox.card_data.engine_status` (`portal/models/sandbox.py:231-240`). Corrective mission C1, still open. | MEDIUM |

## PART B — Security and operational safety (Phase 9)

### B.1 What is genuinely well built

Recorded first, because it is real and should not be lost in the findings below.

- **Fail-closed authentication.** `portal/app.py`'s `_require_authority_login` redirects every
  request without `session["user_id"]` to `/login`. A missing identity does not open the app; it
  means there is nothing to log into. Exemptions are individually justified in the source and are
  narrow: the two HMAC-token blueprints, one named endpoint (`dispatch_api.dispatch_decision`, not
  its whole blueprint), and the driver blueprint, which carries its own gate.
- **Three disjoint session namespaces.** `session["user_id"]`, `session["driver_id"]`, and
  token-only. Neither cookie key can satisfy the other's gate.
- **Real credential hashing.** `werkzeug.security.generate_password_hash` / `check_password_hash`
  (scrypt) for both the Authority PIN and the Driver PIN and recovery word. Hashes are stripped from
  every record before it leaves the module. Failed-attempt lockout on both.
- **A genuine IDOR check.** `stakeholder_evidence_download` requires the evidence record's own
  `load_id` to match the URL, and returns a flat `404` — never a `403` — so the response cannot
  confirm that an evidence id exists under a different load.
- **Safe upload handling.** Extension allowlist, 25 MB cap, and the stored filename is
  **regenerated** as `{evidence_id}.{ext}` (`dispatch/services.py:622-632`), so a hostile filename
  cannot traverse or overwrite.
- **Debug mode defaults off.** `_debug_enabled()` requires an explicit `PORTAL_DEBUG=1`.
- **Machine approval is blocked.** `RESERVED_SYSTEM_IDENTITIES` refuses `PUBLISHER`, `SYSTEM`,
  `AUTOMATION`, `INTELLIGENCE`, `LIBRARY` as approvers.
- **Fail-closed COMI sanitization** by recipient role.
- **Archive integrity** via SHA-256 sidecars verified on read.

### B.2 Findings

| # | Finding | Evidence | Severity |
|---|---|---|---|
| **S-1** | **The HMAC signing secret has a published default.** `dispatch/notifications.py:37` and `cin_lite/email_delivery.py:37` both return `os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret")`. There is no warning and no refusal. Anyone who reads this repository can mint a valid stakeholder token or decision token for **any** `load_id` on a deployment that never set the variable — reading load data, downloading evidence, and actioning decision links. | Both `_secret()` functions | **BLOCKER** |
| **S-2** | **Tokens never expire and cannot be revoked.** `make_stakeholder_token(load_id)` is `HMAC(secret, "dispatch-stakeholder:" + load_id)` — no timestamp, no nonce, no version. The same string is valid forever. Rotating the secret invalidates every link at once, which is the only revocation available. | `dispatch/notifications.py:56-65` | **HIGH** |
| **S-3** | **The Flask session secret has a published default.** `PORTAL_SECRET_KEY` falls back to `"dev-portal-key-change-in-production"`; `check_secret_key()` prints a warning to stderr and **continues**. A deployment that misses the variable has forgeable Authority sessions. | `portal/config.py:9,33,42-45` | **HIGH** |
| **S-4** | **No CSRF protection anywhere.** `grep -rniE "csrf"` across `portal/` returns zero matches. 109 of 218 routes are `POST`/`PATCH`/`PUT`/`DELETE` authenticated by cookie alone. | Route enumeration | **HIGH** |
| **S-5** | **Session cookie flags are never set.** No `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, or `PERMANENT_SESSION_LIFETIME` in `portal/config.py`. Sessions do not expire. | `portal/config.py` | **HIGH** |
| **S-6** | **Integration credentials are stored in plaintext JSON.** `portal/models/integrations_registry.py` persists `api_key`, `credentials`, `token` unencrypted. **The module documents this honestly and at length in its own docstring** — it is a disclosed limitation, not a hidden one — but it remains a plaintext secret store on disk. | `integrations_registry.py:15-30` | **MEDIUM** |
| **S-7** | **`_ensure_storage_dirs()` runs only under `__main__`.** The documented VPS deployment uses gunicorn (`DEPLOY_VPS.md:95`), which never executes it. On a VPS the storage tree is not created at startup. | `portal/app.py`, `if __name__ == "__main__":` | **MEDIUM** |
| **S-8** | **No audit log for data access.** `_log_event` covers 4 of the 12 specified authentication event types; there is no record of who read or downloaded what. | `portal/models/identity.py:184-186` | **MEDIUM** |
| **S-9** | **No rate limiting** on `/login`, `/driver/login`, or the token-verified endpoints. PIN lockout limits guessing per account; nothing limits token enumeration. | Absence | **MEDIUM** |
| **S-10** | **`.env.example` documents every secret variable but nothing enforces them.** Deployment correctness rests entirely on the operator remembering. | `.env.example` (4.7 KB) | **LOW** |

### B.3 The Jules portal — separate and far worse

If `/home/user/Jules` is what is actually running, these apply and they dominate everything above.

| # | Finding | Evidence | Severity |
|---|---|---|---|
| **J-1** | **No authentication of any kind.** `/operations`, `/stakeholder`, and all `/api/v1/*` endpoints are open. | `app.py` — no session, no login, no token check | **BLOCKER** |
| **J-2** | **The Werkzeug debugger was running, and its PIN is committed to the repository.** | `Jules/flask_app.log`: `Debug mode: on` … `Debugger is active!` … `Debugger PIN: 631-326-424` | **BLOCKER** |
| **J-3** | **Bound to `0.0.0.0` by default.** With J-1 and J-2, that is an unauthenticated remote Python console. | `run_portal.sh:10` | **BLOCKER** |
| **J-4** | **No persistence.** All state is a module singleton seeded by `_bootstrap_sample_data()`. Every restart discards everything a driver reported. | `dispatch_spine.py:183` | **BLOCKER for operational use** |
| **J-5** | **POD upload reports success without a file.** `pod_status` is set to `"UPLOADED"` and the response says `"POD uploaded successfully"` even when no file was posted, with `"file_saved": "Simulated upload"`. | `app.py:148-167` | **HIGH — this is a false operational record** |

### B.4 Runtime posture summary

| Question | Answer |
|---|---|
| Can the Dispatch portal be run safely on a laptop, single user, no internet exposure? | **Yes**, with `PORTAL_SECRET_KEY` and `DISPATCH_EMAIL_SECRET` set. |
| Can it be exposed to the internet as it stands? | **No.** S-1 and S-4 must close first. |
| Can stakeholder links be sent to real brokers as it stands? | **No.** S-1 and S-2 must close first — an unset secret makes every link forgeable, and no link can ever be revoked. |
| Can the Jules portal be exposed to anything? | **No.** |
| Is any operational data at risk today? | **No — because there is none.** That is the only reason these findings are not already incidents. |
