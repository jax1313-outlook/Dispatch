# VPS Deployment — Network-Accessible Server

## Prerequisites

- Ubuntu 22.04+ or Debian 12+ (any Linux with Python 3.11+)
- A domain name or static IP
- SSH access

## Blockers to Resolve Before Network Deployment

1. **No authentication** — the portal is open to anyone with the URL.
   Add Flask-Login or a reverse proxy auth layer before exposing.
2. **Flask debug server** — `app.run(debug=True)` must not face the
   network. Use gunicorn behind nginx.

Both are addressed in the setup below.

## Step 1: System Setup

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip nginx
```

## Step 2: Clone and Install

```bash
cd /opt
sudo git clone https://github.com/jax1313-outlook/cin-hybrid.git dispatch
sudo chown -R $USER:$USER /opt/dispatch
cd /opt/dispatch
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install gunicorn
```

## Step 3: Configure Environment

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```
PORTAL_SECRET_KEY=<random-64-char-string>
DISPATCH_EMAIL_SECRET=<random-64-char-string>
PORTAL_HOST=0.0.0.0
DISPATCH_OPERATIONS_ROOT=/opt/dispatch/operations
DISPATCH_ARCHIVE_ROOT=/opt/dispatch/archive
DISPATCH_MEMORY_ROOT=/opt/dispatch/memory
DISPATCH_COMPANY_NAME=<your company>
DISPATCH_MC_NUMBER=<your MC number>
DISPATCH_DOT_NUMBER=<your DOT number>
```

Generate random keys:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Step 4: Create Data Directories

Directories are auto-created on startup when the root env vars are set. Or create manually:

```bash
mkdir -p /opt/dispatch/operations /opt/dispatch/archive /opt/dispatch/memory
```

## Step 5: Gunicorn Service

Create `/etc/systemd/system/dispatch.service`:

```ini
[Unit]
Description=DISPATCH Platform
After=network.target

[Service]
User=dispatch
Group=dispatch
WorkingDirectory=/opt/dispatch
EnvironmentFile=/opt/dispatch/.env
ExecStart=/opt/dispatch/.venv/bin/gunicorn \
    --bind 127.0.0.1:8080 \
    --workers 2 \
    --timeout 120 \
    "portal.app:create_app()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo useradd -r -s /bin/false dispatch
sudo chown -R dispatch:dispatch /opt/dispatch/operations /opt/dispatch/archive /opt/dispatch/memory
sudo systemctl daemon-reload
sudo systemctl enable --now dispatch
sudo systemctl status dispatch
```

## Step 6: Nginx Reverse Proxy

Create `/etc/nginx/sites-available/dispatch`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/dispatch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 7: TLS (HTTPS)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Storage Layout on VPS

```
/opt/dispatch/
├── operations/                      # DISPATCH_OPERATIONS_ROOT
│   ├── Code/
│   ├── Config/
│   ├── Logs/
│   ├── Temp/
│   └── Current Workspace/
│       └── PortalData/
│           ├── dispatch.db          # SQLite database
│           ├── sandbox.json
│           ├── publisher_queue.json
│           └── conflicts.json
├── archive/                         # DISPATCH_ARCHIVE_ROOT
│   ├── CIN/
│   │   ├── Raw/
│   │   ├── Processed/
│   │   ├── Intelligence/
│   │   ├── Summaries/
│   │   ├── Routing/
│   │   ├── Pending/
│   │   ├── Outbox/
│   │   └── Proposals/
│   ├── Loads/
│   ├── POD/
│   ├── Retention/
│   ├── Reports/
│   └── Historical Records/
├── memory/                          # DISPATCH_MEMORY_ROOT
│   ├── library.json
│   ├── intelligence.json
│   ├── archive.json
│   ├── Evidence/                    # Evidence uploads
│   ├── Company Library/
│   ├── Broker Library/
│   ├── Compliance/
│   └── ...
├── .env                             # Environment config (not in git)
└── ...                              # Application code
```

## Operations

### View logs

```bash
sudo journalctl -u dispatch -f
```

### Restart after code update

```bash
cd /opt/dispatch
git pull origin main
sudo systemctl restart dispatch
```

### Database backup

```bash
sqlite3 /opt/dispatch/operations/Current\ Workspace/PortalData/dispatch.db ".backup /tmp/dispatch-backup.db"
cp -r /opt/dispatch/operations /backups/operations-$(date +%Y%m%d)
cp -r /opt/dispatch/archive /backups/archive-$(date +%Y%m%d)
cp -r /opt/dispatch/memory /backups/memory-$(date +%Y%m%d)
```

### Run the CIN-Lite pipeline

```bash
cd /opt/dispatch
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python -m cin_lite.run
```

## Authentication (Required Before Exposing)

The portal currently has no login system. Before making it
network-accessible, add one of:

- **Flask-Login** with a single admin user (bcrypt hash stored in
  SQLite or env var). Wrap routes with `@login_required`.
- **Nginx basic auth** as a quick stopgap:
  ```bash
  sudo apt install -y apache2-utils
  sudo htpasswd -c /etc/nginx/.htpasswd admin
  ```
  Then add to the nginx location block:
  ```nginx
  auth_basic "DISPATCH";
  auth_basic_user_file /etc/nginx/.htpasswd;
  ```

Nginx basic auth is the fastest path to network-safe deployment without
any code changes. It protects every route including the API.
