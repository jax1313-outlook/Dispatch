"""Dispatch Data Engine — freight/load operational backbone.

Seven-object model chain: Load -> LoadVisibilityRecord -> MilestoneEvent
-> EvidenceItem -> ExceptionNotice -> PODPackage -> RetentionArchive.

Persistence: SQLite (stdlib sqlite3, no external dependency).
"""
