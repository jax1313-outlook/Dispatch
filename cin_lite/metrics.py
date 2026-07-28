"""Pipeline metrics and analytics.

Tracks each pipeline run's timing, outcomes, errors, and contract-level stats
as structured JSON lines. Provides summary reporting for operational monitoring.

Metrics are append-only JSONL files under the configured directory (default:
``logs/metrics/``). Each line is a self-contained record so the file can be
tailed, streamed, or loaded incrementally.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from loguru import logger

_METRICS_DIR = Path("logs/metrics")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class RunMetrics:
    """Collects metrics for a single pipeline run."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
        self.started_at = _utc_now()
        self._start_time = time.monotonic()
        self.contracts_acquired = 0
        self.contracts_processed = 0
        self.contracts_by_action: dict[str, int] = {}
        self.errors: list[dict[str, str]] = []
        self.contract_timings: list[dict[str, Any]] = []
        self._current_contract_start: float | None = None

    def record_acquisition(self, count: int) -> None:
        self.contracts_acquired = count
        logger.debug("metrics: acquired {count} contract(s)", count=count)

    @contextmanager
    def track_contract(self, contract_id: str) -> Generator[None, None, None]:
        """Context manager that times processing of a single contract."""
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            self.contracts_processed += 1
            self.contract_timings.append({
                "contract_id": contract_id,
                "elapsed_ms": elapsed_ms,
            })

    def record_action(self, action: str) -> None:
        self.contracts_by_action[action] = self.contracts_by_action.get(action, 0) + 1

    def record_error(self, contract_id: str, stage: str, error: str) -> None:
        self.errors.append({
            "contract_id": contract_id,
            "stage": stage,
            "error": error,
            "timestamp": _utc_now(),
        })

    def finalize(self) -> dict[str, Any]:
        elapsed_s = round(time.monotonic() - self._start_time, 3)
        return {
            "type": "pipeline_run",
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": _utc_now(),
            "elapsed_seconds": elapsed_s,
            "contracts_acquired": self.contracts_acquired,
            "contracts_processed": self.contracts_processed,
            "actions": self.contracts_by_action,
            "error_count": len(self.errors),
            "errors": self.errors,
            "contract_timings": self.contract_timings,
            "avg_contract_ms": (
                round(
                    sum(t["elapsed_ms"] for t in self.contract_timings)
                    / len(self.contract_timings),
                    1,
                )
                if self.contract_timings
                else 0
            ),
        }


def save(record: dict[str, Any], metrics_dir: Path | None = None) -> Path:
    """Append a metrics record to the JSONL log and return the file path."""
    target = metrics_dir or _METRICS_DIR
    _ensure_dir(target)
    path = target / "pipeline.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("metrics: run {run_id} saved ({contracts} contracts, {elapsed}s)",
                run_id=record.get("run_id"), contracts=record.get("contracts_processed"),
                elapsed=record.get("elapsed_seconds"))
    return path


def load_history(metrics_dir: Path | None = None, limit: int = 50) -> list[dict]:
    """Load the most recent pipeline run records."""
    path = (metrics_dir or _METRICS_DIR) / "pipeline.jsonl"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records[-limit:]


def summary_report(metrics_dir: Path | None = None) -> str:
    """Generate a human-readable summary of pipeline run history."""
    records = load_history(metrics_dir)
    if not records:
        return "No pipeline runs recorded yet."

    runs = [r for r in records if r.get("type") == "pipeline_run"]
    if not runs:
        return "No pipeline runs recorded yet."

    total_contracts = sum(r.get("contracts_processed", 0) for r in runs)
    total_errors = sum(r.get("error_count", 0) for r in runs)
    avg_elapsed = sum(r.get("elapsed_seconds", 0) for r in runs) / len(runs)

    all_actions: dict[str, int] = {}
    for r in runs:
        for action, count in r.get("actions", {}).items():
            all_actions[action] = all_actions.get(action, 0) + count

    all_timings = []
    for r in runs:
        all_timings.extend(t.get("elapsed_ms", 0) for t in r.get("contract_timings", []))
    avg_contract_ms = sum(all_timings) / len(all_timings) if all_timings else 0

    lines = [
        "Pipeline Metrics Summary",
        "=" * 50,
        f"Total runs          : {len(runs)}",
        f"First run           : {runs[0].get('started_at', 'n/a')}",
        f"Last run            : {runs[-1].get('started_at', 'n/a')}",
        f"Contracts processed : {total_contracts}",
        f"Total errors        : {total_errors}",
        f"Avg run time        : {avg_elapsed:.2f}s",
        f"Avg per contract    : {avg_contract_ms:.1f}ms",
        "",
        "Action distribution:",
    ]
    for action, count in sorted(all_actions.items(), key=lambda x: -x[1]):
        pct = count / total_contracts * 100 if total_contracts else 0
        lines.append(f"  {action:<20} {count:>4}  ({pct:.0f}%)")

    if total_errors:
        lines.append("")
        lines.append("Recent errors:")
        for r in reversed(runs):
            for err in r.get("errors", []):
                lines.append(f"  [{err.get('timestamp')}] {err.get('contract_id')}: "
                             f"{err.get('stage')} — {err.get('error')}")

    return "\n".join(lines)
