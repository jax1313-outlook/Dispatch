"""Transport adapters — SFTP for production, Local for testing."""

from __future__ import annotations

import shutil
from pathlib import Path


class BaseTransport:
    """Abstract transport interface. All transports implement this."""

    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def list_files(self, remote_path: str, since: float | None = None) -> list[dict]:
        """Return list of {"name": str, "mtime": float} for JSON files at remote_path."""
        raise NotImplementedError

    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        """Download a single file from remote_path to local_path."""
        raise NotImplementedError


class SFTPTransport(BaseTransport):
    """SSH/SFTP transport for pulling records from the VPS."""

    def __init__(self, hostname: str, port: int, username: str,
                 key_path: str, timeout: int = 30):
        self._hostname = hostname
        self._port = port
        self._username = username
        self._key_path = key_path
        self._timeout = timeout
        self._client = None
        self._sftp = None

    def connect(self) -> None:
        try:
            import paramiko
        except ImportError:
            raise RuntimeError(
                "paramiko is required for SFTP sync. Install with: pip install paramiko"
            )

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = paramiko.RSAKey.from_private_key_file(self._key_path)
        self._client.connect(
            hostname=self._hostname,
            port=self._port,
            username=self._username,
            pkey=key,
            timeout=self._timeout,
        )
        self._sftp = self._client.open_sftp()

    def disconnect(self) -> None:
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._client:
            self._client.close()
            self._client = None

    def list_files(self, remote_path: str, since: float | None = None) -> list[dict]:
        if not self._sftp:
            raise RuntimeError("Not connected")
        try:
            attrs = self._sftp.listdir_attr(remote_path)
        except FileNotFoundError:
            return []

        results = []
        for attr in attrs:
            if not attr.filename.endswith(".json"):
                continue
            mtime = float(attr.st_mtime or 0)
            if since is not None and mtime <= since:
                continue
            results.append({"name": attr.filename, "mtime": mtime})
        return results

    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        if not self._sftp:
            raise RuntimeError("Not connected")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._sftp.get(remote_path, str(local_path))


class LocalTransport(BaseTransport):
    """Filesystem transport for testing — reads from a local directory as if it were remote."""

    def __init__(self, base_path: str | Path):
        self._base = Path(base_path)

    def connect(self) -> None:
        if not self._base.exists():
            raise FileNotFoundError(f"Local transport base not found: {self._base}")

    def disconnect(self) -> None:
        pass

    def list_files(self, remote_path: str, since: float | None = None) -> list[dict]:
        full = self._base / remote_path
        if not full.exists():
            return []
        results = []
        for f in sorted(full.iterdir()):
            if not f.is_file() or f.suffix != ".json":
                continue
            mtime = f.stat().st_mtime
            if since is not None and mtime <= since:
                continue
            results.append({"name": f.name, "mtime": mtime})
        return results

    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        src = self._base / remote_path
        dst = Path(local_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
