"""`python -m dispatch_launcher` -- what dispatch.bat and Dispatch.ps1 invoke."""

from __future__ import annotations

import sys

from dispatch_launcher.cli import main

if __name__ == "__main__":
    sys.exit(main())
