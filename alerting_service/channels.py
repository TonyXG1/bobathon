"""Channel routing and delivery (SMS / WhatsApp / Email).

SMS and WhatsApp go through the Twilio Messaging API. Email goes through
SendGrid (Twilio) when a key is configured. When credentials are incomplete or
``TEST_MODE`` is set, the sender runs in **dry-run** mode: it returns a
``simulated`` result (with the reason) instead of calling Twilio, so the whole
pipeline still works end-to-end without sending anything.

Credentials are read from config only and never logged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from config import Settings


@dataclass
class DeliveryResult:
    """Outcome of one alert delivery attempt."""

    status: str  # "sent" | "simulated" | "failed"
    channel: str
    to: str
    message: str
    sid: str | None = None
    error: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class TwilioSender:
    """Sends messages via Twilio, or simulates when not fully configured."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None  # lazily created

    @property
    def client(self):
        """Lazily build a Twilio REST client from whichever auth is present."""
        if self._client is None:
            from twilio.rest import Client

            s = self.settings
            if s.twilio_api_key_sid and s.twilio_api_secret and s.twilio_account_sid:
                self._client = Client(
                    s.twilio_api_key_sid, s.twilio_api_secret, s.twilio_account_sid
                )
            elif s.twilio_account_sid and s.twilio_auth_token:
                self._client = Client(s.twilio_account_sid, s.twilio_auth_token)
            else:  # pragma: no cover - guarded by can_send() before we get here
                raise RuntimeError("Twilio auth not configured")
        return self._client

    def send(self, channel: str, to: str, message: str) -> DeliveryResult:
        """Deliver one message on ``channel`` to ``to``. Never raises."""
        if not to:
            return DeliveryResult("failed", channel, to, message, error="no recipient")

        if not self.settings.can_send(channel):
            return DeliveryResult(
                "simulated",
                channel,
                to,
                message,
                note=self._why_simulated(channel),
            )

        try:
            if channel == "sms":
                return self._send_sms(to, message)
            if channel == "whatsapp":
                return self._send_whatsapp(to, message)
            if channel == "email":
                return self._send_email(to, message)
            return DeliveryResult("failed", channel, to, message, error="unknown channel")
        except Exception as exc:  # noqa: BLE001 - report any Twilio/transport error
            err = str(exc)
            body = getattr(exc, "body", None)
            if body:
                err = f"{err} | {body.decode() if isinstance(body, bytes) else body}"
            return DeliveryResult("failed", channel, to, message, error=err)

    # -- per-channel -------------------------------------------------------

    def _send_sms(self, to: str, message: str) -> DeliveryResult:
        msg = self.client.messages.create(
            body=message, from_=self.settings.twilio_phone_number, to=to
        )
        return DeliveryResult("sent", "sms", to, message, sid=msg.sid)

    def _send_whatsapp(self, to: str, message: str) -> DeliveryResult:
        to_addr = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        msg = self.client.messages.create(
            body=message, from_=self.settings.twilio_whatsapp_from, to=to_addr
        )
        return DeliveryResult("sent", "whatsapp", to, message, sid=msg.sid)

    def _send_email(self, to: str, message: str) -> DeliveryResult:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        from_email = self.settings.sendgrid_from_email or self.settings.twilio_test_email
        mail = Mail(
            from_email=from_email,
            to_emails=to,
            subject="Regulatory Radar — compliance alert",
            plain_text_content=message,
        )
        resp = SendGridAPIClient(self.settings.sendgrid_api_key).send(mail)
        return DeliveryResult("sent", "email", to, message, sid=f"sendgrid-{resp.status_code}")

    def _why_simulated(self, channel: str) -> str:
        s = self.settings
        if s.test_mode:
            return "TEST_MODE is on"
        if channel == "email":
            return "no SENDGRID_API_KEY configured"
        if not s.has_twilio_auth:
            return "Twilio auth incomplete (need TWILIO_ACCOUNT_SID + key/secret)"
        if channel == "sms" and not s.twilio_phone_number:
            return "no TWILIO_PHONE_NUMBER (sender) configured"
        return "sender not configured"
