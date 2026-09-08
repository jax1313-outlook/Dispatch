"""Start Dispatch with everything it creates tagged as rehearsal.

    py -3 scripts\\dispatch_rehearsal.py

Same Dispatch, same screens, same database. The difference is that every record
created while this runs is **tagged as rehearsal at the moment it is created**,
and marked as rehearsal wherever it is displayed. That is the doctrine
(`docs/DISPATCH_REHEARSAL_DATA_DOCTRINE.md`), and the practice exists because
two untagged test records reached the live database an hour apart on 2026-09-07.

WHY THIS IS PYTHON AND NOT A .CMD. The first version opened the session with a
`for /f` loop in batch and captured the id into a variable. It worked and it was
one quoting mistake away from not working -- and the failure mode of *that*
mistake is Dispatch starting with an empty `DISPATCH_REHEARSAL_SESSION`, which
is Dispatch starting **untagged**, which is the one outcome this file exists to
prevent. Here, the session id never leaves the process that uses it.

**It refuses to start Dispatch if the session cannot be opened.** Not starting is
a fine outcome; starting untagged is not.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from dispatch import rehearsal

    print()
    print("  DISPATCH - REHEARSAL MODE")
    print("  " + "-" * 58)
    print()

    try:
        session = rehearsal.start_session(
            label="Rehearsal from the desktop", actor_id="mike",
            note="Started with scripts/dispatch_rehearsal.py")
    except Exception as refused:  # noqa: BLE001
        print("  COULD NOT OPEN A REHEARSAL SESSION.")
        print("  %s: %s" % (type(refused).__name__, refused))
        print()
        print("  DISPATCH WAS NOT STARTED. Nothing can be recorded untagged.")
        return 1

    session_id = session["session_id"]
    os.environ["DISPATCH_REHEARSAL_SESSION"] = session_id

    print("  Session: %s" % session_id)
    print()
    print("  Everything created from now until this window closes is tagged")
    print("  as rehearsal. Open http://127.0.0.1:8080")
    print()
    print("  Press Ctrl-C or close this window to stop.")
    print("  " + "-" * 58)
    print()

    from portal.app import create_app
    from portal.config import Config

    application = create_app()
    try:
        application.run(host=getattr(Config, "HOST", "127.0.0.1"),
                        port=int(getattr(Config, "PORT", 8080)),
                        debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass

    print()
    print("  Dispatch has stopped. Rehearsal session %s is still open." % session_id)
    print("  To close it and say how it went:")
    print()
    print("    py -3 -c \"from dispatch import rehearsal; "
          "rehearsal.close_session('%s', result='PASSED', actor_id='mike')\""
          % session_id)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
