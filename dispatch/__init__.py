"""Dispatch Data Engine — freight/load operational backbone.

Seven-object model chain: Load -> LoadVisibilityRecord -> MilestoneEvent
-> EvidenceItem -> ExceptionNotice -> PODPackage -> RetentionArchive.

Includes a deterministic scoring engine (scoring.py) that computes
Position/HOS assessments, route economics, and overall load scores.

Persistence: SQLite (stdlib sqlite3, no external dependency).
"""
