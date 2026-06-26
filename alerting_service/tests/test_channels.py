"""Tests for delivery/channel routing (channels.py).

Twilio is never actually called: we either run in simulated mode or inject a
fake client.
"""

from channels import TwilioSender
from config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "twilio_account_sid": "",
        "twilio_auth_token": "",
        "twilio_api_key_sid": "",
        "twilio_api_secret": "",
        "twilio_phone_number": "",
        "twilio_test_number": "+15550000000",
        "test_mode": False,
        "sendgrid_api_key": "",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Msg", (), {"sid": "SM_FAKE_123"})()


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_simulated_when_not_configured():
    sender = TwilioSender(_settings())
    res = sender.send("sms", "+15551231234", "hello")
    assert res.status == "simulated"
    assert "incomplete" in (res.note or "") or "TWILIO" in (res.note or "")


def test_simulated_when_test_mode_even_if_configured():
    s = _settings(
        twilio_account_sid="AC1",
        twilio_auth_token="tok",
        twilio_phone_number="+1500",
        test_mode=True,
    )
    sender = TwilioSender(s)
    res = sender.send("sms", "+15551231234", "hello")
    assert res.status == "simulated"
    assert res.note == "TEST_MODE is on"


def test_real_sms_send_with_fake_client():
    s = _settings(twilio_account_sid="AC1", twilio_auth_token="tok", twilio_phone_number="+1500")
    sender = TwilioSender(s)
    sender._client = FakeClient()
    res = sender.send("sms", "+15551231234", "hello")
    assert res.status == "sent"
    assert res.sid == "SM_FAKE_123"
    assert res.channel == "sms"


def test_whatsapp_prefixes_recipient():
    s = _settings(twilio_account_sid="AC1", twilio_auth_token="tok")
    sender = TwilioSender(s)
    fake = FakeClient()
    sender._client = fake
    res = sender.send("whatsapp", "+15551231234", "hi")
    assert res.status == "sent"
    assert fake.messages.calls[0]["to"] == "whatsapp:+15551231234"
    assert fake.messages.calls[0]["from_"].startswith("whatsapp:")


def test_failed_when_client_raises():
    s = _settings(twilio_account_sid="AC1", twilio_auth_token="tok", twilio_phone_number="+1500")
    sender = TwilioSender(s)

    class Boom:
        @property
        def messages(self):
            raise RuntimeError("twilio down")

    sender._client = Boom()
    res = sender.send("sms", "+15551231234", "hello")
    assert res.status == "failed"
    assert "twilio down" in res.error


def test_no_recipient_is_failure():
    sender = TwilioSender(
        _settings(twilio_account_sid="AC1", twilio_auth_token="tok", twilio_phone_number="+1500")
    )
    res = sender.send("sms", "", "hello")
    assert res.status == "failed"
    assert res.error == "no recipient"


def test_email_simulated_without_sendgrid():
    sender = TwilioSender(_settings(twilio_account_sid="AC1", twilio_auth_token="tok"))
    res = sender.send("email", "me@test.example", "hello")
    assert res.status == "simulated"
    assert "SENDGRID" in (res.note or "")
