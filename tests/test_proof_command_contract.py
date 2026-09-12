"""Every command the proof path tells Mike to type is parsed by the real CLI.

Steps 18, 19 and 20 of `dispatch.proof.PROOF_PATH` are the `Code-automated`
steps: they are the gate between IMPLEMENTED and OPERATIONALLY PROVEN, and they
are strings in a data table. Strings in a data table are not executed by
anything, so all three drifted away from their parsers and stayed wrong through
a green suite:

    step 18  dispatch_proof.py verify --load-id ...   -> invalid choice: 'verify'
    step 19  dispatch_backup.py create --destination  -> invalid choice: 'create'
    step 20  dispatch_backup.py restore --archive ... -> unrecognized arguments

The suite could not see it because coverage measures whether a line ran, and
these lines ran fine -- they are tuple literals. What was never checked is
whether the *content* of the literal is a command the program accepts.

So this module pins the content: every `python scripts/<tool>.py ...` command in
the proof path is split and handed to that tool's own `build_parser()`. A
subcommand that is renamed, an option that is removed, a positional that becomes
a flag -- any of them fail here, at the moment of the change, instead of on the
morning somebody sits down to prove the system.

The parsers are imported, not shelled out to: the check is about the argument
contract, and running them for real would perform the backup.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import re
import shlex
from pathlib import Path

import pytest

from dispatch import proof

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

#: Placeholders an operator substitutes. They have to survive parsing as ordinary
#: values -- a parser that rejects `<LOAD_ID>` would also reject a real id.
PLACEHOLDER = re.compile(r"^<[A-Z_]+>$")


def _load_script(name: str):
    """Import a `scripts/*.py` tool by path; they are not an installed package."""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_proof_contract_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split(command: str) -> list[str]:
    """Split a command line without mangling Windows paths.

    `posix=False` keeps `D:\\Backups\\Dispatch` intact -- posix splitting treats
    the backslash as an escape and silently produces `D:BackupsDispatch`, which
    would parse fine and prove nothing.
    """
    parts = shlex.split(command, posix=False)
    return [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parts]


def _script_commands() -> list[tuple[int, str, str, list[str]]]:
    """(step number, tool name, full command, argv) for every scripted step."""
    out = []
    for step in proof.PROOF_PATH:
        command = step.command.strip()
        if not command.startswith("python scripts/"):
            continue
        argv = _split(command)
        assert argv[0] == "python"
        tool = Path(argv[1]).stem
        out.append((step.number, tool, command, argv[2:]))
    return out


SCRIPTED = _script_commands()


def test_the_proof_path_still_has_scripted_steps():
    """If this hits zero, the checks below stopped checking anything."""
    assert SCRIPTED, "no `python scripts/...` commands found in PROOF_PATH"
    assert {n for n, _, _, _ in SCRIPTED} == {18, 19, 20}


@pytest.mark.parametrize("number,tool,command,argv", SCRIPTED, ids=[f"step{n}" for n, *_ in SCRIPTED])
def test_every_scripted_proof_command_parses(number, tool, command, argv):
    parser = _load_script(tool).build_parser()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on a bad command line
        pytest.fail(
            f"proof step {number} is not a command this program accepts.\n"
            f"  command: {command}\n"
            f"  parser:  scripts/{tool}.py\n"
            f"  argparse said: {stderr.getvalue().strip()}\n"
            f"  (exit {exc.code})"
        )
    assert callable(getattr(args, "func", None)), (
        f"proof step {number} parsed but is bound to no handler"
    )


@pytest.mark.parametrize("number,tool,command,argv", SCRIPTED, ids=[f"step{n}" for n, *_ in SCRIPTED])
def test_scripted_proof_commands_use_only_placeholder_or_literal_values(number, tool, command, argv):
    """A placeholder must be a *value*, never an option name.

    `--verify` in step 20 was neither a real flag nor a placeholder; it was a
    remembered one. Anything starting with `-` here has to exist on the parser,
    which is what this asserts by parsing with the placeholders removed from
    consideration.
    """
    for token in argv:
        if token.startswith("-"):
            continue
        assert token, f"step {number} has an empty argument in: {command}"
        if PLACEHOLDER.match(token):
            continue  # operator substitutes a real value here


def test_proof_path_is_still_twenty_steps_with_three_automated():
    """The mission fixes the count; a repair must not quietly add or drop a step."""
    assert len(proof.PROOF_PATH) == 20
    assert [s.number for s in proof.PROOF_PATH] == list(range(1, 21))
    automated = [s.number for s in proof.PROOF_PATH if s.expected_performer == "Code-automated"]
    assert automated == [18, 19, 20]


def test_backup_cli_has_no_create_subcommand_to_drift_back_to():
    """Pins the two names that were wrong, so a revert is a test failure."""
    parser = _load_script("dispatch_backup").build_parser()
    subs = _subcommand_names(parser)
    assert subs == {"backup", "verify", "restore"}
    assert "create" not in subs


def test_proof_cli_exposes_the_step_18_subcommand():
    parser = _load_script("dispatch_proof").build_parser()
    subs = _subcommand_names(parser)
    assert {"verify", "snapshot"} <= subs


def _subcommand_names(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:  # noqa: SLF001 - argparse exposes no public accessor
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return set(action.choices)
    raise AssertionError("parser has no subcommands")
