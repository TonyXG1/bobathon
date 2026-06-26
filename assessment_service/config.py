"""Settings for the assessment service (loaded from env via pydantic-settings).

Simplified, no-database build: each request takes (or fetches) the live
requirements, matches them against the fixed portfolio, and returns findings.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- path bootstrap -------------------------------------------------------
SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parent
for _p in (str(REPO_ROOT), str(SERVICE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATASET_DIR = REPO_ROOT / "dataset"
DEFAULT_PARTNERS_PATH = DATASET_DIR / "partners.json"


class Settings(BaseSettings):
    """Runtime configuration. Field names map to upper-case env vars."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Where to read the portfolio (the FIXED input).
    partners_path: str = str(DEFAULT_PARTNERS_PATH)

    # Upstream extraction service (Part 1) — used when requirements are not
    # supplied directly in the request body.
    extraction_service_url: str = "http://localhost:8081"
    http_timeout: float = 120.0

    # Alert recipients — OUR OWN test endpoints (never a portfolio contact).
    twilio_test_number: str = "+10000000000"
    twilio_test_email: str = "alerts-test@example.com"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
