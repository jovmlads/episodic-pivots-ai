from __future__ import annotations
import logging
import resend
from app.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


def send_scan_report(to_email: str, report_html: str, scan_date: str) -> None:
    """Send scan completion report email."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping email")
        return
    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"Episodic Pivot — Scan Report {scan_date}",
            "html": report_html,
        })
        logger.info("Scan report sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send scan report to %s", to_email)


def send_budget_warning(to_email: str, used: int, budget: int) -> None:
    """Send token budget warning email."""
    if not settings.resend_api_key:
        return
    pct = int((used / budget) * 100)
    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "Episodic Pivot — Token Budget Warning",
            "html": (
                f"<p>You have used <strong>{pct}%</strong> of your monthly AI token budget "
                f"({used:,} / {budget:,} tokens).</p>"
                f"<p>AI analysis will stop when the budget is reached. "
                f"Contact support to increase your limit.</p>"
            ),
        })
    except Exception:
        logger.exception("Failed to send budget warning to %s", to_email)
