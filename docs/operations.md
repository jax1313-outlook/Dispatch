# Operations & Monitoring Guide

## Monitoring Infrastructure

### Built-in Monitoring

CIN-Lite includes three monitoring layers out of the box:

#### 1. Health Checks

```bash
cin-lite --health
```

Checks all subsystems and returns exit code 0 (healthy) or 1 (degraded).
Integrate with any monitoring tool that can run a command and check the exit code.

**Monitored components:**
- Sample data availability
- Archive directory write access
- Rule module registration (expects 9)
- Claude API reachability (when configured)
- SMTP connectivity (when configured)
- SAM.gov API key presence

#### 2. Pipeline Metrics

Every pipeline run writes a structured JSON record to `logs/metrics/pipeline.jsonl`:

```json
{
  "type": "pipeline_run",
  "run_id": "run-20260728-060000",
  "started_at": "2026-07-28T06:00:00Z",
  "completed_at": "2026-07-28T06:00:12Z",
  "elapsed_seconds": 12.345,
  "contracts_acquired": 10,
  "contracts_processed": 10,
  "actions": {"approve_proposal": 3, "flag_review": 5, "reject": 2},
  "error_count": 0,
  "avg_contract_ms": 1234.5
}
```

View the summary:

```bash
cin-lite --metrics
```

#### 3. Structured Logging

All components log via loguru to `logs/cin_lite.log`:

- **Rotation:** 10 MB per file (automatic)
- **Retention:** 30 days (automatic cleanup)
- **Console level:** INFO (colored output)
- **File level:** DEBUG (full detail for troubleshooting)

Log entries include structured context (agent name, contract ID, scores,
flags) for filtering and analysis.

### External Monitoring Integration

#### Uptime / cron monitoring

Wrap the pipeline in a monitoring reporter:

```bash
#!/bin/bash
# run-and-report.sh
cin-lite --action flag_review 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    # Alert on failure (integrate with your alerting system)
    echo "CIN-Lite pipeline failed with exit code $EXIT_CODE" | \
        mail -s "[ALERT] CIN-Lite pipeline failure" ops@yourdomain.com
fi

# Report to uptime monitor (e.g., Healthchecks.io, Cronitor)
curl -fsS -m 10 --retry 5 https://hc-ping.com/your-uuid/$EXIT_CODE
```

#### Log aggregation

Ship `logs/cin_lite.log` and `logs/metrics/pipeline.jsonl` to your log
aggregation system (ELK, Datadog, CloudWatch, etc.):

```bash
# Example: ship to Datadog via the agent
# datadog.yaml
logs:
  - type: file
    path: /opt/cin-lite/logs/cin_lite.log
    service: cin-lite
    source: python
  - type: file
    path: /opt/cin-lite/logs/metrics/pipeline.jsonl
    service: cin-lite
    source: cin-lite-metrics
```

### Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Pipeline success/failure | exit code | Any non-zero |
| Contracts acquired | metrics JSONL | 0 (acquisition failure) |
| Processing time | metrics JSONL | >60s per contract |
| Error count | metrics JSONL | >0 |
| Health check status | `--health` exit code | Non-zero |
| Log file size | filesystem | >500 MB (rotation issue) |
| Archive disk usage | filesystem | >80% capacity |

## Scalability

### Current Capacity

The Phase 1 pipeline processes contracts sequentially. Benchmarked performance:

- **Rule processing:** ~0.5ms per contract (~2000 contracts/s)
- **Full pipeline (deterministic):** ~5ms per contract
- **Full pipeline (with Claude):** ~2-5s per contract (API-bound)
- **Memory:** <50 MB for 100+ contracts

### Scaling Strategies

#### Vertical Scaling (single instance)

For most Phase 1 deployments, a single instance handles the load:

- SAM.gov returns at most ~1000 opportunities per query
- Processing 1000 contracts takes <1s (deterministic) or ~30min (with Claude)
- Increase `CIN_LITE_SAM_LIMIT` as needed

#### Horizontal Scaling (multiple instances)

For higher throughput, run multiple instances with different filters:

```bash
# Instance 1: IT services
CIN_LITE_SAM_NAICS=541512 cin-lite --action flag_review

# Instance 2: Engineering
CIN_LITE_SAM_NAICS=541330 cin-lite --action flag_review

# Instance 3: Cybersecurity
CIN_LITE_SAM_NAICS=541519 cin-lite --action flag_review
```

Each instance writes to its own archive and metrics. No shared state conflicts.

#### Claude API Rate Limits

The Claude API is the primary bottleneck for scaled deployments:

- Use deterministic mode for initial triage (no API calls)
- Reserve Claude for contracts that pass initial filters
- Set `CIN_LITE_SAM_LIMIT` to control batch size
- Consider batching: run deterministic triage first, then Claude on flagged contracts

### Disk Usage Planning

| Component | Size per Contract | 1000 Contracts |
|-----------|-------------------|----------------|
| Raw JSON | ~2 KB | ~2 MB |
| Intelligence JSON | ~5 KB | ~5 MB |
| Summary text | ~500 bytes | ~500 KB |
| Routing JSON | ~1 KB | ~1 MB |
| Proposal (if triggered) | ~10 KB | ~10 MB |
| **Total** | **~18 KB** | **~18 MB** |

At 100 contracts/day, the archive grows ~2 MB/day (~700 MB/year). The
30-day log rotation keeps logs under ~300 MB.

## Backup and Recovery

### Archive Backup

The archive is the system of record. Back it up regularly:

```bash
# Daily backup
tar czf cin-lite-archive-$(date +%Y%m%d).tar.gz Archive/

# Sync to cloud storage
aws s3 sync Archive/ s3://your-bucket/cin-lite-archive/
```

### Recovery

Restore from backup:

```bash
tar xzf cin-lite-archive-20260728.tar.gz -C /opt/cin-lite/
```

The archive is self-contained — each contract's complete analysis is stored
as independent files. No database migration needed.

## Incident Response

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| No contracts acquired | SAM.gov API down or key expired | Check `--health`; falls back to local data automatically |
| All summaries are deterministic | API key missing or expired | Set `ANTHROPIC_API_KEY`; check Anthropic dashboard |
| Emails not sending | SMTP misconfigured | Check `--health`; emails saved to `Archive/Outbox/` |
| Pipeline hangs | Network timeout to SAM.gov/Claude | 30s timeout on all HTTP calls; will fall back |
| Disk full | Archive growth | Clean old archives; adjust log retention |
| Health check DEGRADED | One or more subsystems down | Run `--health` for details; fix the failing component |
