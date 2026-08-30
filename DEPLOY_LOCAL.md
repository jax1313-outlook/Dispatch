# Local Deployment — Windows Desktop (2-Truck Operation)

## Prerequisites

- Python 3.11+
- Git
- (Optional) 2 TB external drive for archive storage

## Quick Start

```
git clone https://github.com/jax1313-outlook/Dispatch.git
cd Dispatch
pip install -e .
cin-portal-init-admin
python portal/app.py
```

Open http://127.0.0.1:8080 in your browser and log in with the PIN you just set.

**`cin-portal-init-admin` is a one-time, interactive step** — it prompts for a user id,
a display name, and a PIN at the terminal (never pipe or script this; PINs aren't
echoed). The portal has a fail-closed login and every route redirects to `/login` until
an identity exists — skipping this step means the app runs but nothing past the login
page is reachable. It refuses to run a second time once an identity exists.

## Storage Layout

### D:\ Ownership Structure (Production)

Set three root variables and the system auto-creates the full folder tree on startup:

```bat
set DISPATCH_OPERATIONS_ROOT=D:\Dispatch Operations
set DISPATCH_ARCHIVE_ROOT=D:\Archive
set DISPATCH_MEMORY_ROOT=D:\Memory
python portal/app.py
```

| Root | Env Var | Contains |
|------|---------|----------|
| `D:\Dispatch Operations` | `DISPATCH_OPERATIONS_ROOT` | Code, Config, Logs, Temp, Current Workspace (SQLite DB, operational JSON) |
| `D:\Archive` | `DISPATCH_ARCHIVE_ROOT` | CIN archive (Raw/Processed/Intelligence), Loads, POD, Retention, Reports |
| `D:\Memory` | `DISPATCH_MEMORY_ROOT` | Library, Intelligence, Evidence uploads, Forms, Templates, Compliance docs |

### Development Mode (No D:\ Vars Set)

When the root env vars are unset, all data stays under the project tree:

| Data              | Default Path         | What's Stored                                  |
|-------------------|----------------------|-------------------------------------------------|
| Portal data       | `portal/data/`       | Sandbox, conflicts, publisher queue (JSON) + SQLite DB |
| CIN-Lite archive  | `cin_lite/Archive/`  | Raw, Processed, Intelligence, Summaries, Routing, Pending, Outbox, Proposals |
| Evidence uploads  | `portal/data/uploads/`| BOL photos, receipts, inspection docs           |
| Library/Intel     | `portal/data/`       | Library and intelligence records (JSON)          |
| Archive records   | `portal/data/`       | Completed archive history (JSON)                 |

### Legacy Env Vars (Still Supported)

These still work and take precedence when set:

| Variable | Overrides | Maps To |
|----------|-----------|---------|
| `DISPATCH_ARCHIVE_PATH` | CIN archive path | `D:\Archive\CIN` |
| `PORTAL_DATA_DIR` | Portal operational data | `D:\Dispatch Operations\Current Workspace\PortalData` |
| `PORTAL_UPLOAD_DIR` | Evidence uploads | `D:\Memory\Evidence` |

## Environment Variables

Copy `.env.example` to `.env` and edit. Load before starting:

**Windows (cmd):**
```bat
for /f "tokens=*" %%i in (.env) do set %%i
python portal/app.py
```

**Windows (PowerShell):**
```powershell
Get-Content .env | Where-Object { $_ -notmatch '^\s*#' -and $_ -ne '' } |
    ForEach-Object { $k,$v = $_.Split('=',2); [Environment]::SetEnvironmentVariable($k,$v) }
python portal/app.py
```

### Required for Real Use

None are required — every variable has a working default. But for
production operations you should set:

| Variable                | Why                                                |
|-------------------------|----------------------------------------------------|
| `DISPATCH_COMPANY_NAME` | Shows on rate confirmations and print documents     |
| `DISPATCH_MC_NUMBER`    | MC number on rate confirmations                     |
| `DISPATCH_DOT_NUMBER`   | DOT number on rate confirmations                    |
| `DISPATCH_COMPANY_ADDRESS` | Company address on printed documents             |
| `DISPATCH_COMPANY_PHONE`  | Contact phone on printed documents               |
| `DISPATCH_COMPANY_EMAIL`  | Contact email on printed documents               |
| `PORTAL_SECRET_KEY`     | Stops the "default secret key" warning              |
| `DISPATCH_EMAIL_SECRET` | Stops the "default HMAC secret" warning             |

### Optional Enhancements

| Variable               | What It Enables                                     |
|------------------------|-----------------------------------------------------|
| `DISPATCH_SMTP_HOST`   | Real email delivery (otherwise .eml files saved)    |
| `ANTHROPIC_API_KEY`    | AI-powered summaries/routing (otherwise deterministic) |
| `DISPATCH_SAM_API_KEY` | Live SAM.gov contract fetching (otherwise sample data) |

## First Operational Load — Step by Step

0. If you haven't already, run `cin-portal-init-admin` once (see Quick Start above) —
   this cannot be skipped; every step below is behind the login screen.
1. Start the portal: `python portal/app.py`
2. Open http://127.0.0.1:8080 and log in with your PIN
3. Go to **Fleet** → create a driver and a truck
4. Go to **Dispatch** → click **New Load** → fill the form
5. Open the load detail → **Assign Driver** + **Assign Equipment**
6. Add milestones as the load progresses (dispatched → picked_up → delivered)
7. Upload evidence (BOL, photos) on the load detail page
8. Click **Generate POD** to bundle evidence
9. Click **Archive Load** to complete the lifecycle
10. View the completed record on the **Archive** page

## Available Launchers

| Command                      | What It Does                                  |
|-----------------------------|------------------------------------------------|
| `python portal/app.py`      | Start the portal web UI                        |
| `.\run_portal.bat`          | Same, via the Windows batch launcher           |
| `python -m cin_lite.run`    | Run the CIN-Lite contract pipeline             |
| `python run_sync.py`        | Run the sync utility (VPS ↔ local)             |
| `.\run_sync.bat`            | Same, via the Windows batch launcher           |
| `python bootstrap_d_drive.py` | Migrate workspace & data into D:\ structure    |
| `.\run_bootstrap_d_drive.bat` | Same, via the Windows batch launcher           |

`run_sync.py` requires `sync/sync_config.json` (copy `sync/sync_config.example.json`
and fill in `vps.hostname`, `vps.username`, `vps.ssh_key_path` — must point to an
existing key file on disk — and `local.primary_path`/`local.backup_path`). It's optional
and only needed if you're syncing between a VPS and a local machine; skip it entirely
for a single-machine local deployment.

## Data Backup

**With D:\ structure set:** Back up the three root directories:
- `D:\Dispatch Operations` — operational database and workspace
- `D:\Archive` — all completed history and contract intelligence
- `D:\Memory` — all business knowledge, evidence, and compliance docs

**Without D:\ structure:** Back up:
- `portal/data/` — SQLite DB, JSON operational data, uploads
- `cin_lite/Archive/` — contract intelligence artifacts
