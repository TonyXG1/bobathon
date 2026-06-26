"""Pytest bootstrap: make the service modules and the shared ``contracts``
package importable regardless of the directory pytest is invoked from.
"""

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parent
for _p in (str(REPO_ROOT), str(SERVICE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
