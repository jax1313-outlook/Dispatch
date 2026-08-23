"""Unit tests for bootstrap_d_drive.py migration utility."""

from pathlib import Path
import os
import pytest
from bootstrap_d_drive import get_target_paths, copy_tree_safe, bootstrap_d_drive


def test_bootstrap_directory_creation(tmp_path, monkeypatch):
    ops_dir = tmp_path / "ops"
    archive_dir = tmp_path / "archive"
    memory_dir = tmp_path / "memory"
    sandbox_dir = tmp_path / "sandbox"

    monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(ops_dir))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_dir))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_dir))
    monkeypatch.setenv("DISPATCH_SANDBOX_EXPORT", str(sandbox_dir))

    targets = get_target_paths()
    assert targets["ops"] == ops_dir
    assert targets["archive"] == archive_dir
    assert targets["memory"] == memory_dir
    assert targets["sandbox"] == sandbox_dir


def test_bootstrap_dry_run_mode(tmp_path):
    ops_dir = tmp_path / "ops"
    archive_dir = tmp_path / "archive"
    memory_dir = tmp_path / "memory"
    sandbox_dir = tmp_path / "sandbox"

    result = bootstrap_d_drive(
        ops_root=str(ops_dir),
        archive_root=str(archive_dir),
        memory_root=str(memory_dir),
        sandbox_root=str(sandbox_dir),
        dry_run=True,
    )

    assert result["copied"] >= 0
    assert not ops_dir.exists()
    assert not sandbox_dir.exists()


def test_bootstrap_file_copying(tmp_path):
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"

    src_dir.mkdir(parents=True)
    file1 = src_dir / "test1.txt"
    file1.write_text("hello world")

    sub_dir = src_dir / "subdir"
    sub_dir.mkdir()
    file2 = sub_dir / "test2.txt"
    file2.write_text("nested file")

    copied, skipped = copy_tree_safe(src_dir, dst_dir, dry_run=False)

    assert copied == 2
    assert (dst_dir / "test1.txt").read_text() == "hello world"
    assert (dst_dir / "subdir" / "test2.txt").read_text() == "nested file"


def test_bootstrap_sandbox_export(tmp_path):
    ops_dir = tmp_path / "ops"
    archive_dir = tmp_path / "archive"
    memory_dir = tmp_path / "memory"
    sandbox_dir = tmp_path / "sandbox"

    result = bootstrap_d_drive(
        ops_root=str(ops_dir),
        archive_root=str(archive_dir),
        memory_root=str(memory_dir),
        sandbox_root=str(sandbox_dir),
        dry_run=False,
    )

    assert result["copied"] > 0
    assert (ops_dir / "Code").exists()
    assert sandbox_dir.exists()
    assert (sandbox_dir / "bootstrap_d_drive.py").exists()
