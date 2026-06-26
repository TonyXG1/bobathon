"""Tests for message formatting (templates.py)."""

from datetime import date

from templates import SMS_MAX_LEN, render_message

from contracts.models import Alert, Finding


def _finding(channel: str, action: str = "Fix it.") -> Finding:
    return Finding(
        company="ACME",
        partner_id="P001",
        product_id="P001-A",
        product="Widget",
        regulation="EU RoHS Directive 2011/65/EU — Annex II (mercury restriction)",
        requirement="No mercury above 0.1%.",
        source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065",
        gap="Contains mercury.",
        deadline=date(2024, 12, 31),
        severity="high",
        recommended_action=action,
        alert=Alert(channel=channel, to="x", message="x"),
    )


def test_sms_message_is_within_limit_and_has_key_fields():
    msg = render_message(_finding("sms"))
    assert len(msg) <= SMS_MAX_LEN
    assert "Widget" in msg
    assert "P001-A" in msg
    assert "2024-12-31" in msg


def test_sms_message_truncates_when_very_long():
    long_action = "Replace the component. " * 40  # force overflow
    msg = render_message(_finding("sms", action=long_action))
    assert len(msg) <= SMS_MAX_LEN


def test_email_message_is_fuller():
    msg = render_message(_finding("email"))
    assert "Requirement:" in msg
    assert "Gap:" in msg
    assert "Source:" in msg
    assert "2024-12-31" in msg


def test_whatsapp_uses_sms_style_compact():
    msg = render_message(_finding("whatsapp"))
    assert len(msg) <= SMS_MAX_LEN
    assert "URGENT" in msg
