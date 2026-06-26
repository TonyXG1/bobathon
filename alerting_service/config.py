"""Settings for the alerting service (loaded from env via pydantic-settings).

Twilio credentials come from the environment only (never hardcoded / logged).
Simplified, no-database build: deliveries are kept in an in-memory log for the
session.
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


class Settings(BaseSettings):
    """Runtime configuration. Field names map to upper-case env vars."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Twilio auth — either (account_sid + auth_token) or
    # (account_sid + api_key_sid + api_secret).
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key_sid: str = ""
    twilio_api_secret: str = ""

    # Senders
    twilio_phone_number: str = ""  # SMS "from"
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # Twilio sandbox

    # OUR OWN test recipients (never a portfolio contact)
    twilio_test_number: str = ""
    twilio_test_email: str = "alerts-test@example.com"

    # Optional real email via SendGrid (Twilio)
    sendgrid_api_key: str = ""
    # The "from" address — MUST be a verified SendGrid sender identity.
    # Falls back to twilio_test_email when blank.
    sendgrid_from_email: str = ""

    # Behaviour
    test_mode: bool = False  # force dry-run even if fully configured

    # Upstream
    assessment_service_url: str = "http://localhost:8082"
    extraction_service_url: str = "http://localhost:8081"
    http_timeout: float = 180.0
    log_level: str = "INFO"

    # Default recipient for the /test-email and /refresh demo endpoints.
    demo_recipient_email: str = "antonsttum@gmail.com"

    # CORS — comma-separated frontend origins; "*" allows any origin (dev default).
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def has_twilio_auth(self) -> bool:
        if not self.twilio_account_sid:
            return False
        if self.twilio_auth_token:
            return True
        return bool(self.twilio_api_key_sid and self.twilio_api_secret)

    def can_send(self, channel: str) -> bool:
        """Whether a real send is possible for the given channel."""
        if self.test_mode:
            return False
        if channel == "email":
            return bool(self.sendgrid_api_key)
        if not self.has_twilio_auth:
            return False
        if channel == "sms":
            return bool(self.twilio_phone_number)
        if channel == "whatsapp":
            return bool(self.twilio_whatsapp_from)
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
