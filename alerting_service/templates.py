"""Message formatting for alerts.

One concise, actionable message per gap. SMS/WhatsApp are capped to keep within
a single segment-ish length (< 300 chars, per AGENTS.md §8).
"""

from __future__ import annotations

from contracts.models import Finding

SMS_MAX_LEN = 300


def _short_regulation(regulation: str) -> str:
    """Trim a long human regulation label to its headline part."""
    for sep in (" — ", " - "):
        if sep in regulation:
            return regulation.split(sep, 1)[0].strip()
    return regulation.strip()


def render_message(finding: Finding, *, channel: str | None = None) -> str:
    """Build the alert text for a finding.

    For SMS/WhatsApp the message is compacted and truncated to ``SMS_MAX_LEN``.
    Email keeps the fuller template.
    """
    channel = channel or finding.alert.channel
    deadline = finding.deadline.isoformat()

    if channel in {"sms", "whatsapp"}:
        msg = (
            f"URGENT: {finding.product} ({finding.product_id}) non-compliant with "
            f"{_short_regulation(finding.regulation)}. Fix by {deadline}: "
            f"{finding.recommended_action} Source: {finding.source_url}"
        )
        if len(msg) > SMS_MAX_LEN:
            # Drop the source URL first, then hard-truncate as a last resort.
            msg = (
                f"URGENT: {finding.product} ({finding.product_id}) non-compliant with "
                f"{_short_regulation(finding.regulation)}. Fix by {deadline}: "
                f"{finding.recommended_action}"
            )
        return msg[:SMS_MAX_LEN].rstrip()

    # email (fuller)
    return (
        f"URGENT: {finding.product} ({finding.product_id}) is non-compliant with "
        f"{finding.regulation}.\n\n"
        f"Requirement: {finding.requirement}\n"
        f"Gap: {finding.gap}\n"
        f"Deadline: {deadline}\n"
        f"Recommended action: {finding.recommended_action}\n"
        f"Source: {finding.source_url}\n"
    )
