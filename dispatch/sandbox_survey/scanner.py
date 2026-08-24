"""Read-only walk of the Sandbox tree.

Every file in the input tree is opened exactly once, in mode ``"rb"``, and is
read twice from that handle's perspective: once streamed through SHA-256 in
full, once capped at `max_bytes` to give the classifier and the sensitive-data
detectors something to look at. Nothing else touches the input tree.

Four failure modes are handled explicitly rather than allowed to abort a run,
because a Sandbox that has been accumulating for years will contain all four
and a tool that dies on the first one never produces a map at all:

*Unreadable files.* A permission error, a file locked by another process, a
device that has gone away. The file is still inventoried, with the OS error
recorded verbatim and a primary class of `Unknown`. It is never silently
dropped -- a silent drop is the one outcome that would make the inventory lie.

*Undecodable bytes.* Sandbox folders hold Windows-1252 exports, UTF-16 Word
detritus and outright binary. The sample is decoded with ``errors="replace"``
so a heuristic can still run over whatever text is in there, and the decoding
outcome is recorded so a reader knows whether the text signals are trustworthy.

*Symlinks and NTFS junctions.* These are never followed -- not into the tree,
not out of it. Following one out of the input root would mean reading, hashing
and classifying files from somewhere Mike never authorised us to look, and
following one back in would double-count. Each link is inventoried as a link,
with its target recorded as inside-root or outside-root, and is never opened.

*Long paths.* See `safety.long_path`.

The output folder is pruned from the walk. It sits inside the read scope by
design, and inventorying it would feed each run's reports into the next run's
map. Its existing contents are captured separately by `scan_prior_output` and
reported as "prior output-folder contents", never classified, never overwritten.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from dispatch.backup import sha256_file

from .safety import is_within, long_path, on_windows

# 64 KiB by default. Large enough that a Markdown note, a source file or an
# exported chat transcript is read essentially in full; small enough that a
# 4 GB disk image contributes 64 KiB of heuristic input instead of 4 GB of
# memory pressure. Overridable from the CLI for a Sandbox full of long documents.
DEFAULT_MAX_BYTES = 65_536

# Extensions whose bytes are text often enough that decoding a sample is
# meaningful. Anything not listed still gets a sample decoded, but is marked
# `text_confidence="binary"` so the classifier weights filename and path
# evidence over content evidence.
TEXT_EXTENSIONS = frozenset({
    ".md", ".markdown", ".txt", ".rst", ".log", ".csv", ".tsv", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml", ".html", ".htm", ".css",
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".sh", ".bash", ".ps1", ".psm1",
    ".bat", ".cmd", ".sql", ".r", ".jsonl", ".ndjson", ".env", ".eml", ".srt",
    ".vtt", ".tex", ".bib", ".gitignore", ".dockerfile", ".makefile", ".properties",
})


@dataclass(frozen=True)
class ScannedFile:
    """One file as the filesystem reported it, before any interpretation.

    Frozen on purpose: the scan result is the evidentiary base of every report,
    and a report generator that could mutate it is a report generator that could
    make the map say something the disk never said. Classification decorates
    this record rather than editing it -- see `classifier.Classification`.
    """

    relpath: str
    absolute: str
    name: str
    suffix: str
    size: int
    modified: str
    sha256: str
    is_symlink: bool = False
    link_target_inside_root: bool | None = None
    read_error: str = ""
    text_confidence: str = "text"
    sample: str = ""
    sample_bytes: int = 0


@dataclass
class ScanResult:
    """Everything the walk found, split into the three populations that matter."""

    files: list[ScannedFile] = field(default_factory=list)
    prior_output_files: list[ScannedFile] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    unreadable_count: int = 0


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def _relpath(path: Path, root: Path) -> str:
    """Relative POSIX-style path, used as the stable identity of a file.

    POSIX separators even on Windows: the same Sandbox surveyed from a mounted
    copy and from the live D: drive then produces comparable identities, and the
    CSV does not need backslash escaping.
    """
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # pragma: no cover - defensive; walk cannot produce this
        return path.as_posix()


def _link_target_inside(path: Path, root: Path) -> bool:
    """Whether a link points back into the input root. Resolution only; no read."""
    try:
        return is_within(path.resolve(), root)
    except OSError:
        return False


def safe_lstat(path: Path) -> tuple[int, str, str]:
    """``(size, modified, error)`` without following a link and without raising.

    ``lstat`` rather than ``stat`` so a dangling link reports the link's own
    metadata instead of blowing up on a target that is not there.
    """
    try:
        stat = path.lstat()
    except OSError as exc:
        return 0, "", f"{type(exc).__name__}: {exc}"
    return stat.st_size, _iso(stat.st_mtime), ""


def _describe_link(path: Path, root: Path, rel: str) -> ScannedFile:
    inside = _link_target_inside(path, root)
    size, modified, error = safe_lstat(path)
    if not error:
        error = (
            "symlink or junction — not followed; target is "
            + ("inside" if inside else "OUTSIDE")
            + " the Sandbox root"
        )
    return ScannedFile(
        relpath=rel, absolute=str(path), name=path.name, suffix=path.suffix.lower(),
        size=size, modified=modified, sha256="", is_symlink=True,
        link_target_inside_root=inside, read_error=error, text_confidence="unread",
    )


def read_sample(path: Path, max_bytes: int) -> tuple[bytes, int]:
    """Read at most `max_bytes` from the head of a file. Mode ``"rb"``, always.

    Returns the raw bytes and the true byte count read. The head rather than a
    random sample because the evidence a classifier can use -- a Markdown title,
    a shebang, a ``BEGIN PRIVATE KEY`` armour line, a document's opening
    paragraph -- is concentrated at the start of a file.
    """
    with open(long_path(path, windows=on_windows()), "rb") as handle:
        chunk = handle.read(max_bytes)
    return chunk, len(chunk)


def _decode(chunk: bytes) -> tuple[str, str]:
    """Decode a sample, and say how much to trust it.

    Returns ``(text, confidence)`` where confidence is one of ``text``,
    ``lossy`` or ``binary``. A NUL byte in the first sample is the cheapest
    reliable binary tell there is, and it matters: without it, a .docx (a ZIP)
    yields enough accidental ASCII to trip content heuristics that were written
    for prose.
    """
    if b"\x00" in chunk:
        return chunk.decode("utf-8", errors="replace"), "binary"
    try:
        return chunk.decode("utf-8"), "text"
    except UnicodeDecodeError:
        # Windows-1252 is the overwhelmingly common non-UTF-8 case in a Windows
        # Sandbox; falling back to it recovers real text from smart quotes and
        # em-dashes instead of littering the sample with replacement characters.
        try:
            return chunk.decode("cp1252"), "lossy"
        except UnicodeDecodeError:
            return chunk.decode("utf-8", errors="replace"), "lossy"


def is_link(path: Path) -> bool:
    """`Path.is_symlink()` calls lstat, and lstat can fail.

    On Windows a file the process cannot stat -- an open handle held
    exclusively, a path on a disconnected network location -- raises here, and
    an exception at this point would abort the whole walk over one bad file.
    Returning False is safe rather than merely convenient: the `stat()` in
    `scan_file` then fails too, and the file is inventoried as Unknown with the
    OS error recorded, which is the correct outcome either way.
    """
    try:
        return path.is_symlink()
    except OSError:
        return False


def scan_file(path: Path, root: Path, max_bytes: int) -> ScannedFile:
    """Inventory one file. Never raises; an unreadable file is still inventoried."""
    rel = _relpath(path, root)
    if is_link(path):
        return _describe_link(path, root, rel)

    suffix = path.suffix.lower()
    try:
        stat = path.stat()
    except OSError as exc:
        return ScannedFile(
            relpath=rel, absolute=str(path), name=path.name, suffix=suffix,
            size=0, modified="", sha256="",
            read_error=f"{type(exc).__name__}: {exc}", text_confidence="unread",
        )

    digest = ""
    sample_text = ""
    sample_len = 0
    confidence = "unread"
    error = ""
    try:
        digest = sha256_file(Path(long_path(path, windows=on_windows())))
        chunk, sample_len = read_sample(path, max_bytes)
        sample_text, confidence = _decode(chunk)
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"

    if not error and suffix and suffix not in TEXT_EXTENSIONS and confidence == "text":
        # An unknown extension that happens to decode cleanly is still not
        # prose we should reason about as prose unless it looks like it.
        confidence = "text" if _looks_like_prose(sample_text) else "binary"

    return ScannedFile(
        relpath=rel, absolute=str(path), name=path.name, suffix=suffix,
        size=stat.st_size, modified=_iso(stat.st_mtime), sha256=digest,
        read_error=error, text_confidence=confidence if not error else "unread",
        sample=sample_text, sample_bytes=sample_len,
    )


def _looks_like_prose(text: str) -> bool:
    """Cheap printable-ratio test. Deterministic, no model, no guessing."""
    if not text:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return printable / len(text) >= 0.90


def walk_input_tree(root: Path, output_root: Path) -> Iterator[tuple[Path, list[str]]]:
    """Yield ``(directory, filenames)`` for the input tree, output folder pruned.

    ``followlinks=False`` keeps `os.walk` out of symlinked and junctioned
    directories entirely; the links themselves still surface as entries so they
    appear in the inventory rather than vanishing from it.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=None):
        here = Path(dirpath)
        # Prune the output folder. Comparing resolved paths rather than names so
        # that a folder merely *called* "Dispatch" elsewhere in the tree is still
        # inventoried -- only the actual designated output folder is excluded.
        keep: list[str] = []
        for name in dirnames:
            child = here / name
            try:
                resolved = child.resolve()
            except OSError:  # pragma: no cover - defensive
                resolved = child
            if resolved == output_root:
                continue
            keep.append(name)
        dirnames[:] = sorted(keep)
        yield here, sorted(filenames)


def scan_prior_output(output_root: Path, max_bytes: int) -> list[ScannedFile]:
    """Inventory whatever is already in the output folder, once, separately.

    These files are reported under their own heading and are never classified,
    never deduplicated against the Sandbox proper, and never overwritten. They
    are almost always this tool's own earlier reports; folding them into the map
    would let the map cite itself as evidence.
    """
    if not output_root.exists():
        return []
    found: list[ScannedFile] = []
    for dirpath, dirnames, filenames in os.walk(output_root, followlinks=False):
        dirnames[:] = sorted(dirnames)
        here = Path(dirpath)
        for name in sorted(filenames):
            found.append(scan_file(here / name, output_root, max_bytes))
    return sorted(found, key=lambda item: item.relpath)


def scan(root: Path, output_root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> ScanResult:
    """Walk the Sandbox and return everything found. Writes nothing, ever."""
    result = ScanResult()
    for directory, filenames in walk_input_tree(root, output_root):
        rel_dir = _relpath(directory, root)
        if rel_dir != ".":
            result.directories.append(rel_dir)
        for name in filenames:
            scanned = scan_file(directory / name, root, max_bytes)
            if scanned.read_error:
                result.unreadable_count += 1
            result.files.append(scanned)
    result.files.sort(key=lambda item: item.relpath)
    result.directories.sort()
    result.prior_output_files = scan_prior_output(output_root, max_bytes)
    if result.unreadable_count:
        result.notes.append(
            f"{result.unreadable_count} entries could not be read or were links that "
            "were deliberately not followed; each is inventoried as Unknown with its "
            "reason recorded, never skipped."
        )
    return result
