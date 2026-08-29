"""Launch the Portal from any working directory.

The portal resolves its data directory relative to the repository root, so a
launcher started elsewhere would write sandbox.json into the wrong folder.
This sets the directory first and then hands over to the real app.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from portal.app import create_app, _ensure_storage_dirs  # noqa: E402
from portal.config import Config  # noqa: E402

if __name__ == "__main__":
    _ensure_storage_dirs()
    app = create_app()
    print("\n  JOE Presentation Layer")
    print("  http://%s:%s/portal\n" % (Config.HOST, Config.PORT))
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)
