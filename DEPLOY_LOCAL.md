# Local Deployment — Windows Desktop (2-Truck Operation)

## Prerequisites

- Python 3.11+
- Git
- (Optional) 2 TB external drive for archive storage

## Quick Start

```
git clone https://github.com/jax1313-outlook/cin-hybrid.git
cd cin-hybrid
pip install -e .
python portal/app.py
```

Open http://127.0.0.1:8080 in your browser.

## Storage Layout

The system writes to three locations — all auto-created on first run:

| Data              | Default Path         | Env Var                  | What's Stored                                  |
|-------------------|----------------------|--------------------------|-------------------------------------------------|
| Portal data       | `portal/data/`       | `PORTAL_DATA_DIR`        | 6 JSON files + SQLite DB + uploads              |
| CIN-Lite archive  | `cin_lite/Archive/`  | `DISPATCH_ARCHIVE_PATH`  | Raw, Processed, Intelligence, Summaries, Routing, Pending, Outbox, Proposals |
| Evidence uploads  | `portal/data/uploads/`| `PORTAL_UPLOAD_DIR`     | BOL photos, receipts, inspection docs           |

### Using an External Drive

To store all data on an external drive (e.g. `D:\`):

1. Create the root folder on the drive (e.g. `D:\Archive`).
2. Set the environment variables before starting:

```bat
set DISPATCH_ARCHIVE_PATH=D:\Archive
set PORTAL_DATA_DIR=D:\Archive\PortalData
python portal/app.py
```

This moves the CIN-Lite file archive, all portal JSON data, the SQLite
database, and evidence uploads to the external drive.

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

1. Start the portal: `python portal/app.py`
2. Open http://127.0.0.1:8080
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

## Data Backup

Back up these paths to protect your data:

- The `PORTAL_DATA_DIR` directory (default `portal/data/`) — contains the
  SQLite database and all JSON operational data
- The `DISPATCH_ARCHIVE_PATH` directory (default `cin_lite/Archive/`) — contains
  all contract intelligence artifacts
- The `PORTAL_UPLOAD_DIR` directory (default `portal/data/uploads/`) — contains
  evidence file uploads

If using an external drive, back up the entire drive root.
