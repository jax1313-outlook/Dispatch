# Deployment Guide

## Deployment Options

### Local Installation

```bash
pip install ".[claude]"
cin-lite --health              # verify
cin-lite --action reject       # test run
```

### Docker

```bash
docker build -t cin-lite .

# Run with sample data
docker run cin-lite --action reject

# Run with live SAM.gov
docker run \
  -e CIN_LITE_SAM_API_KEY=your-key \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v $(pwd)/archive:/app/Archive \
  -v $(pwd)/logs:/app/logs \
  cin-lite --action approve_proposal

# Health check
docker run cin-lite --health
```

### Docker Compose

```yaml
version: "3.9"
services:
  cin-lite:
    build: .
    environment:
      - CIN_LITE_SAM_API_KEY=${CIN_LITE_SAM_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CIN_LITE_SMTP_HOST=${CIN_LITE_SMTP_HOST}
      - CIN_LITE_SMTP_PORT=${CIN_LITE_SMTP_PORT:-587}
      - CIN_LITE_SMTP_USER=${CIN_LITE_SMTP_USER}
      - CIN_LITE_SMTP_PASSWORD=${CIN_LITE_SMTP_PASSWORD}
      - CIN_LITE_EMAIL_FROM=${CIN_LITE_EMAIL_FROM}
      - CIN_LITE_EMAIL_REVIEWER=${CIN_LITE_EMAIL_REVIEWER}
      - CIN_LITE_EMAIL_DOMAIN=${CIN_LITE_EMAIL_DOMAIN}
    volumes:
      - ./archive:/app/Archive
      - ./logs:/app/logs
    command: ["--action", "approve_proposal"]
```

### Scheduled Execution (cron)

```bash
# Run daily at 6 AM, reject all (triage later from archive)
0 6 * * * cd /opt/cin-lite && cin-lite --action flag_review >> /var/log/cin-lite.log 2>&1
```

### Scheduled Execution (systemd timer)

```ini
# /etc/systemd/system/cin-lite.service
[Unit]
Description=CIN-Lite pipeline run

[Service]
Type=oneshot
EnvironmentFile=/etc/cin-lite/env
ExecStart=/usr/local/bin/cin-lite --action flag_review
WorkingDirectory=/opt/cin-lite
User=cinlite
```

```ini
# /etc/systemd/system/cin-lite.timer
[Unit]
Description=Run CIN-Lite daily

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Pre-flight Checklist

Before each deployment, verify:

1. `cin-lite --health` reports HEALTHY
2. `python -m pytest` passes (280+ tests)
3. `coverage report --fail-under=90` passes
4. `bandit -r cin_lite/ -lll -iii` reports no high-severity issues
5. Archive directory is writable and has adequate disk space
6. API keys are set in the environment (not in source code)

## Monitoring

### Pipeline Metrics

Every run automatically records metrics to `logs/metrics/pipeline.jsonl`:

```bash
cin-lite --metrics
```

Shows: total runs, contracts processed, action distribution, average timing,
and any errors.

### Log Files

Logs are written to `logs/cin_lite.log` with automatic rotation:
- Rotation: 10 MB per file
- Retention: 30 days
- Console: INFO level (colored)
- File: DEBUG level (full detail)

### Health Checks

Use `cin-lite --health` for monitoring integration. Returns exit code 0
(healthy) or 1 (degraded). Checks: sample data, archive, rule modules,
Claude API, SMTP, SAM.gov.

## Environment Variables Reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `CIN_LITE_SAM_API_KEY` | No | (local data) | SAM.gov API key |
| `CIN_LITE_SAM_LIMIT` | No | 10 | Max opportunities to pull |
| `CIN_LITE_SAM_POSTED_FROM` | No | 7 days ago | Date range start (MM/DD/YYYY) |
| `CIN_LITE_SAM_POSTED_TO` | No | today | Date range end (MM/DD/YYYY) |
| `CIN_LITE_SAM_NAICS` | No | (none) | NAICS code filter |
| `CIN_LITE_SAM_PTYPE` | No | (none) | Procurement type filter |
| `CIN_LITE_SAM_FETCH_DESCRIPTION` | No | 1 | Fetch full description text |
| `ANTHROPIC_API_KEY` | No | (deterministic) | Claude API key |
| `CIN_LITE_MODEL` | No | claude-opus-4-8 | Claude model override |
| `CIN_LITE_SMTP_HOST` | No | (offline) | SMTP server host |
| `CIN_LITE_SMTP_PORT` | No | 587 | SMTP server port |
| `CIN_LITE_SMTP_USER` | No | (none) | SMTP username |
| `CIN_LITE_SMTP_PASSWORD` | No | (none) | SMTP password |
| `CIN_LITE_SMTP_STARTTLS` | No | 1 | Enable STARTTLS |
| `CIN_LITE_EMAIL_FROM` | No | cin-lite@domain | From address |
| `CIN_LITE_EMAIL_REVIEWER` | No | reviewer@domain | Reviewer address |
| `CIN_LITE_EMAIL_DOMAIN` | No | cin-lite.local | Email domain |

## Security

- API keys must be set via environment variables, never in source code
- The Dockerfile runs as a non-root user (`cinlite`)
- Bandit static analysis runs in CI on every push
- URL scheme validation prevents SSRF on acquisition URLs
- SMTP credentials are never logged or archived
