#!/usr/bin/env python3
"""Dispatch Synchronization Utility launcher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync.cli import main

if __name__ == "__main__":
    sys.exit(main())
