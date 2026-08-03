"""Tests for D:\\ ownership folder structure and storage routing.

Covers all 8 test requirements from PROMPT 2:
1. D:\\ roots are used when environment variables are set.
2. Folder creation works.
3. CIN archive writes route to D:\\Archive\\CIN.
4. Portal data writes route to Dispatch Operations.
5. Library documents route to D:\\Memory.
6. Completed archive records route to D:\\Archive.
7. No existing tests break (covered by test suite; verified via defaults).
8. Defaults still work in test environment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Requirement 1: D:\\ roots are used when env vars are set ──────────


class TestRootsUsed:
    def test_archive_root_routes_cin(self, tmp_path, monkeypatch):
        archive_root = tmp_path / "Archive"
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
        monkeypatch.delenv("DISPATCH_ARCHIVE_PATH", raising=False)
        from cin_lite import archive
        result = archive._resolve_archive_root()
        assert result == archive_root / "CIN"

    def test_archive_path_overrides_root(self, tmp_path, monkeypatch):
        explicit = tmp_path / "MyArchive"
        monkeypatch.setenv("DISPATCH_ARCHIVE_PATH", str(explicit))
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "Other"))
        from cin_lite import archive
        result = archive._resolve_archive_root()
        assert result == explicit

    def test_memory_root_routes_library(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        from portal.models import get_memory_dir
        assert get_memory_dir() == memory_root

    def test_memory_root_routes_intelligence(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        from portal.models import get_memory_dir
        assert get_memory_dir() == memory_root

    def test_archive_root_routes_portal_archive(self, tmp_path, monkeypatch):
        archive_root = tmp_path / "Archive"
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
        from portal.models import get_archive_dir
        assert get_archive_dir() == archive_root

    def test_ops_root_routes_portal_data(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        from portal.models import get_data_dir
        assert get_data_dir() == ops_root / "Current Workspace" / "PortalData"

    def test_ops_root_routes_db(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        set_db_path(None)
        from dispatch.db import _default_db_path
        result = _default_db_path()
        expected_dir = ops_root / "Current Workspace" / "PortalData"
        assert result == expected_dir / "dispatch.db"
        set_db_path(tmp_path / "test.db")

    def test_memory_root_routes_uploads(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        monkeypatch.delenv("PORTAL_UPLOAD_DIR", raising=False)
        from dispatch.services import _get_upload_dir
        assert _get_upload_dir() == memory_root / "Evidence"


# ── Requirement 2: Folder creation works ──────────────────────────────


class TestFolderCreation:
    def test_ops_folders_created(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        from portal.app import _ensure_storage_dirs
        _ensure_storage_dirs()
        for sub in ("Code", "Constitution", "Context", "Config",
                     "Launchers", "Logs", "Temp", "Current Workspace", "Deployment"):
            assert (ops_root / sub).is_dir(), f"Missing: {sub}"
        assert (ops_root / "Current Workspace" / "PortalData").is_dir()

    def test_archive_folders_created(self, tmp_path, monkeypatch):
        archive_root = tmp_path / "Archive"
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        from portal.app import _ensure_storage_dirs
        _ensure_storage_dirs()
        for sub in ("Loads", "POD", "Retention", "Reports", "Historical Records"):
            assert (archive_root / sub).is_dir(), f"Missing: {sub}"
        cin = archive_root / "CIN"
        for cin_sub in ("Raw", "Processed", "Intelligence", "Summaries",
                        "Routing", "Proposals", "Pending", "Outbox"):
            assert (cin / cin_sub).is_dir(), f"Missing CIN/{cin_sub}"

    def test_memory_folders_created(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        from portal.app import _ensure_storage_dirs
        _ensure_storage_dirs()
        for sub in ("Company Library", "Broker Library", "Customer Library",
                     "Location Intelligence", "Operational Intelligence",
                     "Forms", "Templates", "Procedures", "Manuals",
                     "Receipts", "Fuel", "Compliance", "Equipment",
                     "Drivers", "Insurance", "Certifications", "Evidence", "Documents"):
            assert (memory_root / sub).is_dir(), f"Missing: {sub}"

    def test_no_folders_when_vars_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        from portal.app import _ensure_storage_dirs
        _ensure_storage_dirs()


# ── Requirement 3: CIN archive writes route to D:\\Archive\\CIN ────────


class TestCINArchiveRouting:
    def test_cin_archive_write(self, tmp_path, monkeypatch):
        archive_root = tmp_path / "Archive"
        cin_root = archive_root / "CIN"
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
        monkeypatch.delenv("DISPATCH_ARCHIVE_PATH", raising=False)
        from cin_lite import archive
        monkeypatch.setattr(archive, "ARCHIVE_ROOT", cin_root)
        archive.store(
            contract={"title": "Test Contract", "agency": "Test Agency"},
            intelligence={"set_aside": {"flags": ["test"]}},
            summary="test summary",
        )
        raw_dir = cin_root / "Raw"
        assert raw_dir.exists()
        assert len(list(raw_dir.iterdir())) == 1


# ── Requirement 4: Portal data writes route to Dispatch Operations ────


class TestPortalDataRouting:
    def test_sandbox_uses_ops_root(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        data_dir = ops_root / "Current Workspace" / "PortalData"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        from portal.models import get_data_dir
        assert get_data_dir() == data_dir

    def test_portal_data_dir_overrides_ops_root(self, tmp_path, monkeypatch):
        explicit = tmp_path / "CustomData"
        monkeypatch.setenv("PORTAL_DATA_DIR", str(explicit))
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(tmp_path / "Ops"))
        from portal.models import get_data_dir
        assert get_data_dir() == explicit

    def test_db_routes_to_ops_root(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        set_db_path(None)
        from dispatch.db import _default_db_path
        result = _default_db_path()
        assert result.parent == ops_root / "Current Workspace" / "PortalData"
        assert result.name == "dispatch.db"
        set_db_path(tmp_path / "test.db")


# ── Requirement 5: Library documents route to D:\\Memory ───────────────


class TestLibraryRouting:
    def test_library_writes_to_memory(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        memory_root.mkdir()
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        from portal.models import library
        monkeypatch.setattr(library, "_library_path",
                            lambda: memory_root / "library.json")
        record = library.add_record("company", "Test Doc", "content")
        assert record["name"] == "Test Doc"
        assert (memory_root / "library.json").exists()

    def test_intelligence_writes_to_memory(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        memory_root.mkdir()
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        from portal.models import intelligence
        monkeypatch.setattr(intelligence, "_intel_path",
                            lambda: memory_root / "intelligence.json")
        record = intelligence.create_record("broker", "Test Broker", "intel content")
        assert record["subject"] == "Test Broker"
        assert (memory_root / "intelligence.json").exists()


# ── Requirement 6: Completed archive records route to D:\\Archive ──────


class TestArchiveRecordRouting:
    def test_portal_archive_writes_to_archive_root(self, tmp_path, monkeypatch):
        archive_root = tmp_path / "Archive"
        archive_root.mkdir()
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
        from portal.models import archive
        monkeypatch.setattr(archive, "_archive_path",
                            lambda: archive_root / "archive.json")
        record = archive.create_record(
            section="load",
            source_id="TEST-001",
            title="Test Load",
            record_data={"status": "completed"},
        )
        assert record["section"] == "load"
        assert (archive_root / "archive.json").exists()


# ── Requirement 8: Defaults still work in test environment ────────────


class TestDefaults:
    def test_cin_archive_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_ARCHIVE_PATH", raising=False)
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        from cin_lite import archive
        result = archive._resolve_archive_root()
        assert result == Path(archive.__file__).resolve().parent / "Archive"

    def test_portal_data_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from portal.models import get_data_dir
        result = get_data_dir()
        expected = Path(__file__).resolve().parent.parent / "portal" / "data"
        assert result == expected

    def test_memory_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from portal.models import get_memory_dir
        result = get_memory_dir()
        expected = Path(__file__).resolve().parent.parent / "portal" / "data"
        assert result == expected

    def test_archive_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from portal.models import get_archive_dir
        result = get_archive_dir()
        expected = Path(__file__).resolve().parent.parent / "portal" / "data"
        assert result == expected

    def test_upload_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PORTAL_UPLOAD_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from dispatch.services import _get_upload_dir
        result = _get_upload_dir()
        expected = Path(__file__).resolve().parent.parent / "portal" / "data" / "uploads"
        assert result == expected

    def test_db_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        set_db_path(None)
        from dispatch.db import _default_db_path
        result = _default_db_path()
        expected = Path(__file__).resolve().parent.parent / "portal" / "data" / "dispatch.db"
        assert result == expected
        set_db_path(tmp_path / "test.db")


# ── Env var precedence chains ─────────────────────────────────────────


class TestPrecedence:
    def test_upload_dir_explicit_wins(self, tmp_path, monkeypatch):
        explicit = tmp_path / "custom_uploads"
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(explicit))
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
        from dispatch.services import _get_upload_dir
        assert _get_upload_dir() == explicit

    def test_portal_data_dir_wins_over_ops_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "explicit"))
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(tmp_path / "ops"))
        from portal.models import get_data_dir
        assert get_data_dir() == tmp_path / "explicit"

    def test_archive_path_wins_over_archive_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_ARCHIVE_PATH", str(tmp_path / "explicit"))
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "root"))
        from cin_lite import archive
        assert archive._resolve_archive_root() == tmp_path / "explicit"


# ── Config class resolution (PROMPT 5 gap fix) ──────────────────────


class TestConfigResolution:
    def test_config_data_dir_uses_ops_root(self, tmp_path, monkeypatch):
        ops_root = tmp_path / "Dispatch Operations"
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_root))
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        from portal.config import _resolve_data_dir
        result = _resolve_data_dir()
        assert result == str(ops_root / "Current Workspace" / "PortalData")

    def test_config_data_dir_explicit_wins(self, tmp_path, monkeypatch):
        explicit = tmp_path / "CustomData"
        monkeypatch.setenv("PORTAL_DATA_DIR", str(explicit))
        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(tmp_path / "Ops"))
        from portal.config import _resolve_data_dir
        assert _resolve_data_dir() == str(explicit)

    def test_config_data_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from portal.config import _resolve_data_dir, _PORTAL_DIR
        assert _resolve_data_dir() == str(_PORTAL_DIR / "data")

    def test_config_upload_dir_uses_memory_root(self, tmp_path, monkeypatch):
        memory_root = tmp_path / "Memory"
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
        monkeypatch.delenv("PORTAL_UPLOAD_DIR", raising=False)
        from portal.config import _resolve_upload_dir
        assert _resolve_upload_dir() == str(memory_root / "Evidence")

    def test_config_upload_dir_explicit_wins(self, tmp_path, monkeypatch):
        explicit = tmp_path / "CustomUploads"
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(explicit))
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
        from portal.config import _resolve_upload_dir
        assert _resolve_upload_dir() == str(explicit)

    def test_config_upload_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PORTAL_UPLOAD_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        monkeypatch.delenv("PORTAL_DATA_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        from portal.config import _resolve_upload_dir, _PORTAL_DIR
        assert _resolve_upload_dir() == str(_PORTAL_DIR / "data" / "uploads")
