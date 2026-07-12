"""Offline guard: the decision path never imports the similarity layer.

Runs in a fresh interpreter so a previously polluted ``sys.modules`` in the
test process can't mask (or fake) a violation.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = """
import sys
sys.path.insert(0, {repo!r})
sys.path.insert(0, {assessment!r})
import engine                # the matcher (decision path)
import storage.repository    # its only database surface
assert "storage.similarity" not in sys.modules, (
    "decision path transitively imported storage.similarity"
)
"""


def test_decision_path_does_not_load_similarity():
    pytest.importorskip("sqlalchemy")
    script = _SCRIPT.format(repo=str(REPO_ROOT), assessment=str(REPO_ROOT / "assessment_service"))
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
