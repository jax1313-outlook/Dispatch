r"""The safety perimeter for the Sandbox survey: root validation and the single
permitted writer.

This module exists because the survey's whole value proposition is that it is
*provably* read-only against Mike's Sandbox. A survey tool that "tries not to"
modify its input is worth nothing; the guarantee has to be structural, so that
the only way to break it is to delete code that a test is watching.

Three structural decisions carry that guarantee:

*One writer, one root.* Nothing anywhere in this package writes to disk except
`OutputWriter.write_text`. That method resolves its destination and refuses --
by raising, not by logging -- any path that does not land strictly inside the
resolved output root. A bug elsewhere that computes a destination of
`../../notes.md` therefore produces a refusal, not a clobbered input file.

*Exclusive creation, never truncation.* The writer opens with mode ``"x"``.
That is the only file mode in this package other than ``"rb"``. Mode ``"x"``
fails if the target exists, so the tool cannot overwrite a prior output even if
the timestamped filename scheme were to collide. There is no ``"w"``, no
``"a"``, no ``"r+"`` anywhere, and no code path that renames, moves, merges or
deletes anything -- not behind a flag, not behind a confirmation prompt, not at
all. `tests/test_sandbox_survey.py` asserts that by parsing this package's own
source.

*The output root must live inside the input root, or the run is refused.* That
looks backwards at first glance -- surely writing outside the read scope is
safer? It is not, for this mission. The mission designates
``D:\Sandbox\Play Pen\Dispatch`` as the one permitted write location and
creating it as the one permitted structural change. Accepting an output root
somewhere else would mean the tool had been pointed at a directory nobody
authorised. Refusing is the fail-closed reading, and it makes the containment
rule a single comparison instead of a policy argument.

Because the output root is inside the read scope, the scanner must prune it
from its own walk -- see `scanner.walk_input_tree`. Otherwise the second run
would inventory the first run's reports and the map would slowly fill with its
own reflection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Windows refuses paths longer than 260 characters through the normal API. A
# Sandbox that has accumulated "Copy of Copy of ..." trees hits that ceiling,
# and the failure mode we must avoid is the tool silently skipping those files
# -- an inventory with a hole in it is worse than no inventory. The ``\\?\``
# prefix opts into the extended-length API.
_WINDOWS_PATH_LIMIT = 240


class SandboxSafetyError(RuntimeError):
    """A safety rule was violated. Always fatal; never caught and continued.

    Every raise site carries a plain-language reason that the CLI prints
    verbatim, because the operator reading it is Mike, not a developer.
    """


def long_path(path: Path, *, windows: bool) -> str:
    """Return the string form to hand to ``open()``, extended-length if needed.

    Split out from the call sites and given an explicit `windows` flag rather
    than reading `os.name` inline so that the Windows branch is reachable from
    a Linux test run. The tool ships to a Windows machine but is developed and
    proven on Linux; a branch that only executes on the target machine is a
    branch nobody has ever seen work.
    """
    text = str(path)
    if not windows:
        return text
    if text.startswith("\\\\?\\"):
        return text
    if len(text) < _WINDOWS_PATH_LIMIT:
        return text
    if text.startswith("\\\\"):
        # UNC share: \\server\share -> \\?\UNC\server\share
        return "\\\\?\\UNC" + text[1:]
    return "\\\\?\\" + text


def on_windows() -> bool:
    """Isolated so `long_path`'s callers stay testable on either platform."""
    return os.name == "nt"


def is_within(child: Path, parent: Path) -> bool:
    """True when `child` is `parent` itself or sits underneath it.

    Both sides are expected to be already-resolved absolute paths; resolving
    here as well would hide a caller that forgot to, and forgetting to is
    exactly how a containment check gets bypassed by a ``..`` segment.

    Note for the Windows target: `Path.resolve()` normalises case on NTFS in
    practice, so the comparison below is case-correct there. On a
    case-sensitive filesystem it is exact, which is stricter, not looser.
    """
    if child == parent:
        return True
    return parent in child.parents


def resolve_roots(sandbox_root: Path | str, output_root: Path | str) -> tuple[Path, Path]:
    """Validate the pair of roots, or refuse the whole run.

    Returns ``(input_root, output_root)`` fully resolved. Raises
    `SandboxSafetyError` -- it never returns a partially-valid pair, because a
    caller that got a pair back and then checked a flag is a caller that will
    one day forget to check the flag.
    """
    raw_input_root = Path(sandbox_root)
    raw_output_root = Path(output_root)

    if not raw_input_root.exists():
        raise SandboxSafetyError(
            f"the Sandbox path does not exist on this machine: {raw_input_root}"
        )
    if not raw_input_root.is_dir():
        raise SandboxSafetyError(
            f"the Sandbox path is not a folder: {raw_input_root}"
        )

    resolved_input = raw_input_root.resolve()
    # The output root usually does not exist yet, so it is resolved
    # non-strictly. Path.resolve() is non-strict by default in 3.11.
    resolved_output = raw_output_root.resolve()

    if resolved_output == resolved_input:
        raise SandboxSafetyError(
            "the output folder may not be the Sandbox folder itself; it must be a "
            f"subfolder of it (got {resolved_output})"
        )
    if not is_within(resolved_output, resolved_input):
        raise SandboxSafetyError(
            "refusing to run: the output folder must be inside the Sandbox folder. "
            f"Sandbox={resolved_input} output={resolved_output}"
        )
    if resolved_output.exists() and not resolved_output.is_dir():
        raise SandboxSafetyError(
            f"the output path exists but is not a folder: {resolved_output}"
        )
    return resolved_input, resolved_output


def prepare_output_root(output_root: Path, *, dry_run: bool) -> None:
    """Create the one folder this tool is permitted to create.

    Creating the output folder is the single structural change the mission
    authorises. Under `dry_run` even that is skipped -- a dry run leaves the
    Sandbox byte-for-byte and folder-for-folder as it found it.
    """
    if dry_run:
        return
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SandboxSafetyError(
            f"refusing to run: the output folder could not be created: {output_root} ({exc})"
        ) from exc


@dataclass
class OutputWriter:
    """The only thing in this package that writes to disk.

    Deliberately not frozen: it accumulates `written`, which the CLI prints and
    the tests assert over. Deliberately not given a `force` or `overwrite`
    option: there is no legitimate reason for this tool to replace a file, and
    an option that exists is an option that gets passed.
    """

    output_root: Path
    dry_run: bool = False
    written: list[Path] = field(default_factory=list)

    def destination(self, name: str) -> Path:
        """Resolve `name` inside the output root, refusing anything that escapes.

        `name` is always generated by this package, never supplied by an
        operator or read from the Sandbox -- but it is checked anyway, because
        the check costs nothing and the day it is removed is the day a filename
        starts being derived from a scanned file's own name.
        """
        candidate = Path(name)
        if candidate.is_absolute():
            raise SandboxSafetyError(
                f"refusing to write: output name must be relative, got {name!r}"
            )
        if ".." in candidate.parts:
            raise SandboxSafetyError(
                f"refusing to write: output name may not contain '..', got {name!r}"
            )
        resolved = (self.output_root / candidate).resolve()
        if not is_within(resolved, self.output_root):
            raise SandboxSafetyError(
                "refusing to write outside the designated output folder: "
                f"{resolved} is not inside {self.output_root}"
            )
        if resolved == self.output_root:
            raise SandboxSafetyError(
                f"refusing to write: {name!r} resolves to the output folder itself"
            )
        return resolved

    def emit(self, name: str, text: str) -> Path:
        """Create a new file inside the output root. Never replaces one.

        Named `emit` rather than `write_text` so that `Path.write_text` can be
        banned outright by name in the package's own AST test. A guarantee that
        has to distinguish "our safe write_text" from "pathlib's dangerous
        write_text" is a guarantee with an exception in it.

        Mode ``"x"`` is load-bearing: it turns "the timestamp collided" from a
        silently destroyed prior report into a loud refusal. UTF-8 with an
        explicit newline so the Markdown and CSV are byte-identical whether the
        tool runs on Windows or Linux, which is what makes the hash of an output
        comparable between Mike's run and a reproduction here.
        """
        target = self.destination(name)
        if self.dry_run:
            self.written.append(target)
            return target
        if target.exists():
            raise SandboxSafetyError(
                f"refusing to overwrite an existing output file: {target}"
            )
        with open(target, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        self.written.append(target)
        return target
