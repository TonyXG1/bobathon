"""Pytest bootstrap: make the repo root (contracts, storage) and the
assessment service (engine, portfolio — needed by the parity tests)
importable regardless of the directory pytest is invoked from.
"""

import sys
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = STORAGE_DIR.parent
ASSESSMENT_DIR = REPO_ROOT / "assessment_service"
for _p in (str(REPO_ROOT), str(ASSESSMENT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
