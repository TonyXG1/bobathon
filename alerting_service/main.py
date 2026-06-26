"""Alerting Service (Part 3) — FastAPI app (simplified, no database).

Sends one alert per compliance gap on the partner's ``preferred_channel`` to
OUR OWN test endpoints (never a portfolio contact), via Twilio. Deliveries are
kept in an in-memory log for the session.

Endpoints:
* ``GET  /health``                  — liveness probe.
* ``POST /alerts``                  — send alerts for a list of findings (body).
* ``POST /dispatch``                — full pipeline: fetch findings from the
                                      assessment service, then send.
* ``GET  /alerts/log``              — delivery history (this session).
* ``GET  /alerts/log/{product_id}`` — deliveries for one product.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from channels import TwilioSender
from config import get_settings
from fastapi import FastAPI, HTTPException, Query
from templates import render_message

from contracts.models import Finding

logging.basicConfig(level=get_settings().log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulatory Radar — Alerting Service",
    description="Dispatch one alert per compliance gap via Twilio (to OUR test endpoints).",
    version="0.2.0",
)

# In-memory delivery log (no database in this simplified build).
ALERTS_LOG: list[dict] = []


def _recipient(finding: Finding) -> str:
    """Recipient for the finding's channel.

    Email goes to the address carried on the finding (the partner's contact
    email, set by the assessment service). SMS/WhatsApp go to OUR test number.
    """
    s = get_settings()
    channel = finding.alert.channel
    if channel == "email":
        return finding.alert.to or s.twilio_test_email
    return s.twilio_test_number or finding.alert.to


def _send_findings(
    findings: list[Finding], *, limit: int | None, only_channel: str | None
) -> list[dict]:
    settings = get_settings()
    sender = TwilioSender(settings)
    results: list[dict] = []
    sent = 0
    for finding in findings:
        channel = finding.alert.channel
        if only_channel and channel != only_channel:
            continue
        if limit is not None and sent >= limit:
            break
        to = _recipient(finding)
        message = render_message(finding, channel=channel)
        result = sender.send(channel, to, message).as_dict()
        entry = {
            "product_id": finding.product_id,
            "partner_id": finding.partner_id,
            "company": finding.company,
            "sent_at": datetime.now(UTC).isoformat(),
            **result,
        }
        ALERTS_LOG.append(entry)
        results.append(entry)
        sent += 1
    return results


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "alerting"}


@app.post("/alerts")
def send_alerts(
    findings: list[Finding],
    limit: int | None = Query(default=None, description="Max alerts to send."),
    only_channel: str | None = Query(
        default=None, description="Only send on this channel (sms/whatsapp/email)."
    ),
) -> list[dict]:
    """Send alerts for the findings supplied in the request body."""
    if not findings:
        raise HTTPException(status_code=400, detail="No findings supplied.")
    return _send_findings(findings, limit=limit, only_channel=only_channel)


@app.post("/dispatch")
def dispatch(
    limit: int | None = Query(default=None, description="Max alerts to send."),
    only_channel: str | None = Query(
        default=None, description="Only send on this channel (sms/whatsapp/email)."
    ),
) -> list[dict]:
    """Full pipeline: fetch findings from the assessment service, then send."""
    settings = get_settings()
    url = f"{settings.assessment_service_url.rstrip('/')}/findings"
    try:
        resp = httpx.get(url, timeout=settings.http_timeout)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch findings from assessment service: {exc}",
        ) from exc
    findings = [Finding.model_validate(item) for item in resp.json()]
    return _send_findings(findings, limit=limit, only_channel=only_channel)


@app.get("/alerts/log")
def get_log() -> list[dict]:
    return ALERTS_LOG


@app.get("/alerts/log/{product_id}")
def get_log_for_product(product_id: str) -> list[dict]:
    return [e for e in ALERTS_LOG if e.get("product_id") == product_id]
