from datetime import datetime
from typing import List, Dict, Any


def build_teaser(
    product_display_name: str,
    iso_week: str,
    window_weeks: int,
    themes: List[Dict[str, Any]],
    doc_url: str = "",
) -> Dict[str, str]:
    """
    Build an email teaser with subject and HTML body.

    Returns a dict with 'subject' and 'body' keys suitable for the
    MCP server's /create_email_draft endpoint.
    """
    now_ist = datetime.now().strftime("%Y-%m-%d %H:%M IST")

    subject = f"{product_display_name} Weekly Review Pulse — {iso_week}"

    # Build theme bullet list
    theme_bullets = ""
    for t in themes:
        name = t.get("theme_name", "Unknown Theme")
        summary = t.get("summary", "")
        theme_bullets += f"<li><strong>{name}</strong> — {summary}</li>\n"

    # CTA link
    if doc_url:
        cta = f'<a href="{doc_url}">Read full report →</a>'
    else:
        cta = "<em>(Google Doc link will be available after delivery)</em>"

    body = f"""<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2>{product_display_name} — Weekly Review Pulse — {iso_week}</h2>
<p>
    Period: Last {window_weeks} weeks (rolling) · Source: Google Play Store<br>
    Generated: {now_ist}
</p>

<h3>Top Themes This Week</h3>
<ul>
{theme_bullets}</ul>

<p style="margin-top: 20px;">
    <strong>{cta}</strong>
</p>

<hr style="border: none; border-top: 1px solid #ccc; margin-top: 30px;">
<p style="font-size: 12px; color: #888;">
    This is an automated weekly pulse generated from public Google Play Store reviews.
    The full report with quotes and action ideas is in the linked Google Doc.
</p>
</body>
</html>"""

    return {"subject": subject, "body": body}
