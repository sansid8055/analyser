from datetime import datetime
from typing import List, Dict, Any


def build_section(
    product_display_name: str,
    iso_week: str,
    window_weeks: int,
    themes: List[Dict[str, Any]],
) -> str:
    """
    Build a plain-text section for appending to a Google Doc via the MCP server.

    The MCP server's /append_to_doc endpoint accepts plain text (no rich
    formatting), so we produce a readable, structured text block.
    """
    now_ist = datetime.now().strftime("%Y-%m-%d %H:%M IST")

    lines: list[str] = []

    # --- Heading ---
    heading = f"{product_display_name} — Weekly Review Pulse — {iso_week}"
    lines.append(heading)
    lines.append("=" * len(heading))
    lines.append("")
    lines.append(
        f"Period: Last {window_weeks} weeks (rolling) · "
        f"Source: Google Play Store · Generated: {now_ist}"
    )
    lines.append("")

    # --- Top Themes ---
    lines.append("Top Themes")
    lines.append("-" * 10)
    for t in themes:
        name = t.get("theme_name", "Unknown Theme")
        summary = t.get("summary", "")
        lines.append(f"• {name} — {summary}")
    lines.append("")

    # --- Real User Quotes ---
    lines.append("Real User Quotes")
    lines.append("-" * 16)
    for t in themes:
        for q in t.get("quotes", []):
            lines.append(f'• "{q}"')
    lines.append("")

    # --- Action Ideas ---
    lines.append("Action Ideas")
    lines.append("-" * 12)
    for t in themes:
        for a in t.get("action_ideas", []):
            title = a.get("title", "")
            detail = a.get("detail", "")
            lines.append(f"• {title} — {detail}")
    lines.append("")

    # --- Who This Helps ---
    lines.append("Who This Helps")
    lines.append("-" * 14)
    lines.append("• Product — Prioritize roadmap from recurring themes")
    lines.append("• Support — Spot repeating complaints and quality issues")
    lines.append("• Leadership — Fast health snapshot tied to customer voice")
    lines.append("")

    return "\n".join(lines)
