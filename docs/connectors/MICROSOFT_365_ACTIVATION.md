# Microsoft 365 — what has to be true before anything is LIVE

**Status of everything in this document: `UNCONFIGURED`.** No Microsoft call has
been made from this repository. The flows below are implemented to Microsoft's
published protocols and are exercised by the suite against recorded response
shapes — that is evidence of software behaviour, not of connectivity, and this
document does not present it as more. Nothing becomes `LIVE` until an operator
performs the steps here on a real account.

---

## 1. Why delegated device code, and not a client secret

`dispatch/connectors/outlook_connector.py` declares
`auth_method = "oauth_client_credentials"` with a tenant id, client id and client
secret. That is **app-only** Microsoft Graph, and for this program it is wrong
twice:

- It requires an Entra ID (Azure AD) tenant and an administrator's consent. It
  **cannot authenticate a personal Microsoft account** — an `outlook.com` address
  — at all.
- Its permissions are tenant-wide. Reading one operator's calendar should not
  require a grant that can read every mailbox in an organisation.

**Device code** is the flow that fits a one-operator business on a laptop:

- Dispatch prints a short code; the operator signs in on any browser as
  themselves.
- The token carries exactly that person's own permissions.
- It works on personal Microsoft accounts *and* on work/school accounts.
- **No client secret sits on the laptop.** A public client does not hold one.

Implemented in `dispatch/msauth.py`. There is deliberately no
`DISPATCH_MS_CLIENT_SECRET` setting anywhere in this repository.

## 2. Why SMTP with a password is not the answer either

`cin_lite/email_delivery.py` sends with `smtplib.login(user, password)` on port
587 — SMTP AUTH basic authentication. **Microsoft 365 disables SMTP AUTH by
default on every tenant** and is retiring it. The one path in this program that
actually reaches brokers is built on the mechanism being switched off.

Two supported replacements are implemented, both in `dispatch/transport/`:

| Transport | What it is | When to choose it |
|---|---|---|
| `graph` | Graph `POST /me/sendMail` as the signed-in operator | Preferred. Puts the message in the operator's **Sent Items**, so a broker's reply lands in a thread that exists in Outlook. Needs no relay host. |
| `smtp_oauth2` | The same `smtp.office365.com`, XOAUTH2 instead of a password | Smallest change for an install already sending through Office 365 SMTP: host, port and message identical, only the credential changes. |
| `smtp_basic` | Username and password | Any non-Microsoft relay. Still supported; removing it would break working installs. |
| `file_outbox` | Writes a `.eml`, reports `SIMULATED` | The default with nothing configured. **Not delivery.** |

`python -m dispatch_launcher transports` prints all four and which one is
selected.

## 3. Registering the application (once, by Mike)

1. Sign in at <https://portal.azure.com> → **Microsoft Entra ID** → **App
   registrations** → **New registration**.
2. Name it anything (`Dispatch`). Under **Supported account types** choose
   **Accounts in any organizational directory and personal Microsoft accounts**
   — the last part is what makes an `outlook.com` account work.
3. Leave **Redirect URI** empty. Register.
4. Open **Authentication** → **Advanced settings** → set **Allow public client
   flows** to **Yes**. This is the setting device code requires; without it the
   sign-in fails with `unauthorized_client`.
5. Copy the **Application (client) ID**.
6. Do **not** create a client secret. Nothing here uses one.

### Permissions

Under **API permissions**, add these **delegated** Microsoft Graph permissions:

| Permission | Why |
|---|---|
| `offline_access` | So the refresh token exists at all; otherwise every send needs a fresh sign-in. |
| `Mail.Send` | To send as the operator. |
| `Calendars.Read` | The Outlook connector reads and never writes (CLAUDE.md §5.5). |
| `User.Read` | To show which account is connected. |

`Mail.Read` is deliberately **not** requested. Dispatch does not read the
operator's mailbox and the scope should say so.

## 4. On the laptop

```
setx DISPATCH_MS_CLIENT_ID <the Application (client) ID>
python -m dispatch_launcher connect-microsoft
```

The launcher prints a URL and a code. Sign in as the account Dispatch should
send mail as. When it finishes:

```
python -m dispatch_launcher transports
```

should show `LIVE -- Microsoft Graph as <address>`.

### What "connected" does and does not prove

A successful sign-in proves the token exchange worked. It does **not** prove a
message has been delivered. Send one and look in **Sent Items**. Until then the
honest state of delivery is `UNVERIFIED`, and the twenty-step operational proof
treats it that way.

## 5. Settings

| Variable | Default | Meaning |
|---|---|---|
| `DISPATCH_MS_CLIENT_ID` | — | Application (client) ID. Absent = `UNCONFIGURED`, and every Microsoft path refuses rather than attempting an anonymous call. |
| `DISPATCH_MS_TENANT` | `common` | `common` accepts personal and work accounts. Set to a tenant id only to restrict to one organisation. |
| `DISPATCH_MS_TOKEN_CACHE` | `$DISPATCH_MEMORY_ROOT/auth/microsoft-token.json` | Where the refresh token is kept. |
| `DISPATCH_TRANSPORT` | — | Pin one transport by id while migrating, so adding a client id does not silently move every outbound message onto Graph mid-week. |

### Token storage

`dispatch/msauth.TokenCache` takes injected `protect`/`unprotect` functions. The
host decides how the refresh token is protected — Windows DPAPI ties the file to
the user account so a copied cache is useless elsewhere. On platforms with no
standard-library equivalent the file is written unprotected under the operating
system's own permissions, and this document says so rather than implying more.

**Disconnecting:** `python -m dispatch_launcher disconnect-microsoft` removes the
stored token. Revoking the grant itself is done at
<https://account.live.com/consent/Manage> (personal) or in Entra ID (work).

## 6. What is still not built

Honest scope, so nobody reads this page as a completed integration:

- **Calendar read** is a declared connector capability with no HTTP call behind
  it. The auth and transport layers this document describes are what it was
  missing; the Graph calendar query itself is not written.
- **OneDrive, SharePoint, Teams and Word** have no adapters in this repository.
- **Delta synchronisation** for calendar is not implemented; there is no local
  calendar store for it to update, and by CLAUDE.md §5.5 there must not be one —
  Outlook is the scheduling authority and Dispatch presents it.
- **Retry** for Graph distinguishes retryable (`429`, `5xx`) from terminal
  (`4xx`) and records the outcome in `delivery_attempts`. Resending is triggered
  by an operator, never by a timer.
