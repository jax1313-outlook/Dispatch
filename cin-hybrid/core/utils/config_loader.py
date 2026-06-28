"""Configuration loading for CIN-Hybrid (YAML or JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> Any:
    """Load configuration from a YAML (.yaml/.yml) or JSON (.json) file.

    YAML support requires PyYAML; a clear error is raised if it isn't installed.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError("PyYAML is required to load YAML config files") from exc
        return yaml.safe_load(text)

    if suffix == ".json":
        return json.loads(text)

    raise ValueError(f"Unsupported config format: {p.suffix!r} (expected .yaml, .yml, or .json)")
