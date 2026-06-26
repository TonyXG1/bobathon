"""Settings for the extraction service (loaded from env via pydantic-settings).

Simplified, no-database build: the service queries live EU sources on each
request and returns the results directly. Endpoints and politeness knobs come
from the environment / a local ``.env`` (see ``.env.example`` at the repo root).
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- path bootstrap -------------------------------------------------------
# The shared ``contracts`` package lives at the repo root. Make sure it is
# importable whether the service is launched via uvicorn (cwd = service dir)
# or imported from tests.
SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parent
for _p in (str(REPO_ROOT), str(SERVICE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class Settings(BaseSettings):
    """Runtime configuration. Field names map to upper-case env vars."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # EUR-Lex / CELLAR
    cellar_sparql_endpoint: str = "http://publications.europa.eu/webapi/rdf/sparql"

    # Politeness / limits
    http_timeout: float = 60.0
    contact_email: str = "contact@example.com"
    log_level: str = "INFO"

    # CORS — comma-separated frontend origins; "*" allows any origin (dev default).
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def user_agent(self) -> str:
        """Polite User-Agent with contact info (see SOURCES.md §7.1)."""
        return f"RegulatoryRadar/1.0 (extraction; {self.contact_email})"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
