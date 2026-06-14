#!/usr/bin/env python3
"""Generate HTML intelligence briefs for morning, midday, and EOD.

Usage:
    python3 generate_brief.py [morning|midday|eod]

Auto-detects period from current hour if not specified:
    6-11   → morning
    11-16  → midday
    16+    → eod

Output: ~/.local/share/software-of-you/output/brief_{period}.html
        Opens automatically after generation.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Paths ---
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).parent.parent)
DATA_DIR = Path.home() / ".local" / "share" / "software-of-you"
DB_PATH = DATA_DIR / "soy.db"
OUTPUT_DIR = Path(PLUGIN_ROOT) / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_period(arg=None):
    if arg in ("morning", "midday", "eod"):
        return arg
    hour = datetime.now().hour
    if hour < 11:
        return "morning"
    elif hour < 17:
        return "midday"
    else:
        return "eod"


def q(sql, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def scalar(sql, params=()):
    rows = q(sql, params)
    if rows:
        return list(rows[0].values())[0]
    return 0


def fmt_time(iso):
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", ""))
        now = datetime.now()
        delta = dt - now
        if delta.total_seconds() < 0:
            mins = abs(int(delta.total_seconds() / 60))
            if mins < 60:
                return f"{mins}m ago"
            return f"{int(mins/60)}h ago"
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            return f"in {mins}m"
        if mins < 1440:
            return f"in {int(mins/60)}h"
        return dt.strftime("%a %-I:%M %p")
    except Exception:
        return iso[:16] if len(iso) > 16 else iso


def fmt_received(iso):
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", ""))
        now = datetime.now()
        delta = now - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            return f"{mins}m ago"
        if mins < 1440:
            return f"{int(mins/60)}h ago"
        return dt.strftime("%a %-I:%M %p")
    except Exception:
        return iso[:16] if len(iso) > 16 else iso


def gather_data(period):
    now = datetime.now()

    # Time window for "new since last brief"
    if period == "morning":
        since = (now - timedelta(hours=14)).isoformat()  # since ~4pm yesterday
        label = "overnight"
    elif period == "midday":
        since = now.replace(hour=6, minute=0, second=0).isoformat()
        label = "since 6am"
    else:
        since = now.replace(hour=12, minute=0, second=0).isoformat()
        label = "since noon"

    # Unread emails (all)
    unread = q("""
        SELECT e.subject, e.from_name, e.from_address, e.received_at,
               e.snippet, e.thread_id, ga.label as account_label
        FROM emails e
        LEFT JOIN google_accounts ga ON e.account_id = ga.id
        WHERE e.is_read = 0
        ORDER BY e.received_at DESC
        LIMIT 20
    """)

    # New emails since last brief window
    new_emails = q("""
        SELECT e.subject, e.from_name, e.received_at, ga.label as account_label
        FROM emails e
        LEFT JOIN google_accounts ga ON e.account_id = ga.id
        WHERE e.received_at > ? AND e.direction = 'inbound'
        ORDER BY e.received_at DESC
        LIMIT 20
    """, (since,))

    # Today's calendar events
    today_start = now.replace(hour=0, minute=0, second=0).isoformat()
    today_end = now.replace(hour=23, minute=59, second=59).isoformat()
    today_events = q("""
        SELECT title, start_time, end_time, location, attendees, ga.label as account_label
        FROM calendar_events ce
        LEFT JOIN google_accounts ga ON ce.account_id = ga.id
        WHERE start_time BETWEEN ? AND ?
          AND status != 'cancelled'
        ORDER BY start_time ASC
    """, (today_start, today_end))

    # Upcoming events (next 2 days, not today)
    tomorrow_end = (now + timedelta(days=2)).replace(hour=23, minute=59).isoformat()
    upcoming_events = q("""
        SELECT title, start_time, end_time, ga.label as account_label
        FROM calendar_events ce
        LEFT JOIN google_accounts ga ON ce.account_id = ga.id
        WHERE start_time > ? AND start_time <= ?
          AND status != 'cancelled'
        ORDER BY start_time ASC
        LIMIT 5
    """, (today_end, tomorrow_end))

    # Open commitments
    open_commitments = q("""
        SELECT description, owner, due_date, source_call_id
        FROM commitments
        WHERE status = 'open'
        ORDER BY due_date ASC NULLS LAST
        LIMIT 10
    """)

    # Top contacts by recent activity
    active_contacts = q("""
        SELECT c.name, c.company,
               MAX(e.received_at) as last_email
        FROM contacts c
        JOIN emails e ON e.contact_id = c.id
        GROUP BY c.id
        ORDER BY last_email DESC
        LIMIT 8
    """)

    # Pending transcripts
    pending_transcripts = scalar("""
        SELECT COUNT(*) FROM transcripts WHERE analyzed = 0
    """)

    return {
        "period": period,
        "label": label,
        "since": since,
        "now": now,
        "unread": unread,
        "new_emails": new_emails,
        "today_events": today_events,
        "upcoming_events": upcoming_events,
        "open_commitments": open_commitments,
        "active_contacts": active_contacts,
        "pending_transcripts": pending_transcripts,
    }


def render_html(d):
    period = d["period"]
    now = d["now"]

    period_config = {
        "morning": {
            "title": "Morning Brief",
            "greeting": f"Good morning, Kerry.",
            "subtitle": f"Here's what's waiting — {now.strftime('%A, %B %-d')}",
            "accent": "#16a34a",
            "icon": "☀",
        },
        "midday": {
            "title": "Midday Update",
            "greeting": "Midday check-in.",
            "subtitle": f"What's moved since this morning — {now.strftime('%-I:%M %p')}",
            "accent": "#2563eb",
            "icon": "◑",
        },
        "eod": {
            "title": "End of Day",
            "greeting": "Day's done.",
            "subtitle": f"Here's what happened — {now.strftime('%A, %B %-d')}",
            "accent": "#7c3aed",
            "icon": "◐",
        },
    }[period]

    # Build sections
    sections = []

    # Calendar section
    if d["today_events"]:
        events_html = ""
        for ev in d["today_events"]:
            t = fmt_time(ev["start_time"])
            acct = f'<span class="acct">{ev["account_label"]}</span>' if ev.get("account_label") else ""
            events_html += f"""
            <div class="item">
                <div class="item-main">{ev["title"]}</div>
                <div class="item-meta">{t} {acct}</div>
            </div>"""
        sections.append(("calendar", "📅 Today", events_html, len(d["today_events"])))

    # Unread emails
    if d["unread"]:
        emails_html = ""
        for em in d["unread"][:10]:
            t = fmt_received(em["received_at"])
            sender = em.get("from_name") or em.get("from_address", "")
            acct = f'<span class="acct">{em["account_label"]}</span>' if em.get("account_label") else ""
            subj = em.get("subject", "(no subject)")
            emails_html += f"""
            <div class="item">
                <div class="item-main">{subj}</div>
                <div class="item-meta">{sender} · {t} {acct}</div>
            </div>"""
        sections.append(("email", f"📬 Unread ({len(d['unread'])})", emails_html, len(d["unread"])))

    # New since last brief
    if d["new_emails"]:
        new_html = ""
        for em in d["new_emails"]:
            t = fmt_received(em["received_at"])
            acct = f'<span class="acct">{em["account_label"]}</span>' if em.get("account_label") else ""
            new_html += f"""
            <div class="item">
                <div class="item-main">{em.get("subject", "(no subject)")}</div>
                <div class="item-meta">{em.get("from_name", "")} · {t} {acct}</div>
            </div>"""
        sections.append(("new", f"🆕 New {d['label']} ({len(d['new_emails'])})", new_html, len(d["new_emails"])))

    # Commitments
    if d["open_commitments"]:
        comm_html = ""
        for c in d["open_commitments"]:
            due = f' · due {c["due_date"][:10]}' if c.get("due_date") else ""
            owner = c.get("owner") or "you"
            comm_html += f"""
            <div class="item">
                <div class="item-main">{c["description"]}</div>
                <div class="item-meta">{owner}{due}</div>
            </div>"""
        sections.append(("commits", f"✋ Open commitments ({len(d['open_commitments'])})", comm_html, len(d["open_commitments"])))

    # Upcoming
    if d["upcoming_events"]:
        up_html = ""
        for ev in d["upcoming_events"]:
            t = fmt_time(ev["start_time"])
            up_html += f"""
            <div class="item">
                <div class="item-main">{ev["title"]}</div>
                <div class="item-meta">{t}</div>
            </div>"""
        sections.append(("upcoming", "🗓 Coming up", up_html, len(d["upcoming_events"])))

    # Pending transcripts
    if d["pending_transcripts"]:
        sections.append(("transcripts", f"🎙 {d['pending_transcripts']} unanalyzed transcripts", "", d["pending_transcripts"]))

    # Build section HTML
    sections_html = ""
    for (_, title, body, count) in sections:
        sections_html += f"""
        <div class="card">
            <div class="card-title">{title}</div>
            {body}
        </div>"""

    if not sections_html:
        sections_html = '<div class="card"><div class="empty">All clear. Nothing urgent.</div></div>'

    # Stats bar
    stats_html = f"""
        <div class="stat"><span class="stat-n">{len(d['unread'])}</span><span class="stat-l">unread</span></div>
        <div class="stat"><span class="stat-n">{len(d['today_events'])}</span><span class="stat-l">meetings today</span></div>
        <div class="stat"><span class="stat-n">{len(d['open_commitments'])}</span><span class="stat-l">open commitments</span></div>
        <div class="stat"><span class="stat-n">{len(d['new_emails'])}</span><span class="stat-l">new {d['label']}</span></div>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{period_config['title']} · {now.strftime('%b %-d')}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ font-family: 'Inter', system-ui, sans-serif; }}
  body {{ background: #f8fafc; color: #0f172a; margin: 0; padding: 0; }}
  .accent {{ color: {period_config['accent']}; }}
  .card {{ background: white; border-radius: 12px; padding: 20px 24px; margin-bottom: 14px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: 1px solid #f1f5f9; }}
  .card-title {{ font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase;
                 letter-spacing: .05em; margin-bottom: 12px; }}
  .item {{ padding: 8px 0; border-bottom: 1px solid #f8fafc; }}
  .item:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .item-main {{ font-size: 14px; font-weight: 500; color: #1e293b; line-height: 1.4; }}
  .item-meta {{ font-size: 12px; color: #94a3b8; margin-top: 2px; }}
  .acct {{ background: #f1f5f9; color: #64748b; border-radius: 4px; padding: 1px 5px;
           font-size: 11px; margin-left: 4px; }}
  .stat {{ text-align: center; }}
  .stat-n {{ display: block; font-size: 28px; font-weight: 600; color: {period_config['accent']}; line-height: 1; }}
  .stat-l {{ display: block; font-size: 11px; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: .04em; }}
  .empty {{ color: #94a3b8; font-size: 14px; text-align: center; padding: 12px 0; }}
  .ts {{ font-size: 11px; color: #cbd5e1; margin-top: 4px; }}
</style>
</head>
<body>
<div style="max-width:640px;margin:0 auto;padding:32px 16px">

  <!-- Header -->
  <div style="margin-bottom:28px">
    <div style="font-size:28px;margin-bottom:2px">{period_config['icon']}</div>
    <h1 style="font-size:24px;font-weight:600;margin:0 0 4px">{period_config['greeting']}</h1>
    <p style="color:#64748b;margin:0;font-size:14px">{period_config['subtitle']}</p>
    <p class="ts">{now.strftime('%I:%M %p')}</p>
  </div>

  <!-- Stats -->
  <div class="card" style="margin-bottom:20px">
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px">
      {stats_html}
    </div>
  </div>

  <!-- Sections -->
  {sections_html}

  <div style="text-align:center;padding:24px 0;color:#cbd5e1;font-size:11px">
    Software of You · {now.strftime('%A, %B %-d at %-I:%M %p')}
  </div>
</div>
</body>
</html>"""


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    period = get_period(arg)

    data = gather_data(period)
    html = render_html(data)

    out_path = OUTPUT_DIR / f"brief_{period}.html"
    out_path.write_text(html)

    print(f"Brief generated: {out_path}")

    # Auto-open
    os.system(f'open "{out_path}"')


if __name__ == "__main__":
    main()
