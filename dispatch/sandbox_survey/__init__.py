"""Read-only survey of a Windows Sandbox working folder.

Built for the DISPATCH operational-readiness mission, whose first pass over
``D:\\Sandbox\\Play Pen`` must be provably read-only: nothing moved, renamed,
deleted, overwritten, deduplicated, converted, archived, uploaded or committed,
and nothing found in the tree ever executed.

The package is laid out so each of those guarantees lives in one place:

    safety      root validation and the single write choke-point
    scanner     the read-only walk; mode "rb" is the only input file mode
    classifier  deterministic, rule-based classification with named rules
    duplicates  exact SHA-256 and two independent near-duplicate signals
    sensitive   sensitive-material detection that emits path + category only
    survey      orchestration; produces a dict, writes nothing
    reports     the nine documents, as pure functions over that dict

WHY THIS LIVES UNDER `dispatch/` AND NOT `tools/`. Two reasons, both practical.
The repository's coverage configuration measures `cin_lite`, `dispatch` and
`portal`; a safety-critical package outside those trees would be the one part
of the codebase whose branches nobody counts, which is precisely backwards for
code whose entire value is a guarantee about what it does not do. And
`pyproject.toml` discovers packages matching `dispatch*`, so a `tools/` package
would not be installed by `pip install -e .` and would not be importable from
an installed distribution -- the CLI would work from a checkout and fail
everywhere else.

This package NEVER runs against the real Sandbox from CI or from an agent
session. It is executed by hand, by Mike, on the machine that holds the folder.
See `docs/readiness/SANDBOX_SURVEY_PROCEDURE.md`.
"""

from __future__ import annotations

from .classifier import CLASSES, INTERPRETATION_RULES, LOCKED_DOCTRINE, Classification, classify
from .duplicates import DuplicateGroup, DuplicateReport, find_duplicates
from .reports import DOCUMENTS, generate_all
from .safety import OutputWriter, SandboxSafetyError, is_within, resolve_roots
from .scanner import DEFAULT_MAX_BYTES, ScanResult, ScannedFile, scan
from .sensitive import CATEGORIES, SensitiveFinding, detect
from .survey import (
    AUTHORITY_DECLARATION,
    READ_ONLY_DECLARATION,
    TOOL_VERSION,
    SurveyResult,
    absent_result,
    run_survey,
    write_reports,
)

__all__ = [
    "AUTHORITY_DECLARATION",
    "CATEGORIES",
    "CLASSES",
    "DEFAULT_MAX_BYTES",
    "DOCUMENTS",
    "INTERPRETATION_RULES",
    "LOCKED_DOCTRINE",
    "READ_ONLY_DECLARATION",
    "TOOL_VERSION",
    "Classification",
    "DuplicateGroup",
    "DuplicateReport",
    "OutputWriter",
    "SandboxSafetyError",
    "ScanResult",
    "ScannedFile",
    "SensitiveFinding",
    "SurveyResult",
    "absent_result",
    "classify",
    "detect",
    "find_duplicates",
    "generate_all",
    "is_within",
    "resolve_roots",
    "run_survey",
    "scan",
    "write_reports",
]
