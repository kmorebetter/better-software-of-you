#!/usr/bin/env python3
"""Deterministic HTML renderer for Software of You.

Replaces token-by-token, Claude-authored HTML generation with instant,
deterministic rendering. Reads the DB's computed views + base tables and the
existing Jinja templates, then writes every structural page + entity page to
``output/`` (a symlink to ~/.local/share/software-of-you/output).

Nothing here is invented: every displayed number traces to a query or view
column, and NULLs render as "—". No network, no Claude. Autoescape stays ON;
the only raw-HTML channels are the whitelisted ``type:'html'`` module_view
sections, and every DB value spliced into them is ``markupsafe.escape``'d first.

CLI:
    python3 scripts/render.py [all|dashboard|entities|modules|stale-narratives]

Ports the machinery of mcp-server/.../tools/views.py (dashboard + entity page
logic, nav context, time helpers, slug whitelist) but writes to output/ instead
of views/, and sources entity narratives from the DB instead of a Claude arg.
"""

import hashlib
import json
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path
from types import SimpleNamespace

# --- Resolve plugin root and put the MCP package on the path -----------------
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "mcp-server" / "src"))

import jinja2  # noqa: E402  (needs sys.path first)
from markupsafe import escape, Markup  # noqa: E402  (ships with jinja2)

from software_of_you.db import (  # noqa: E402
    execute, execute_many, execute_write, rows_to_dicts, get_installed_modules,
)

OUTPUT_DIR = PLUGIN_ROOT / "output"
TEMPLATES_DIR = PLUGIN_ROOT / "mcp-server" / "src" / "software_of_you" / "templates"


# =============================================================================
# Shared helpers (ported verbatim in behavior from tools/views.py)
# =============================================================================

def _safe_slug(name: str, fallback: str = "view") -> str:
    """Whitelist a name to a filesystem-safe slug (``[a-z0-9-]``)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or fallback


def _get_env() -> jinja2.Environment:
    """Jinja env with autoescape ON for HTML (see views.py audit note)."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
    )


def _parse_dt(iso_str: str) -> datetime | None:
    """Parse an ISO datetime to a NAIVE local datetime (tz stripped safely).

    Handles values with any UTC offset (e.g. ``-07:00``), not just ``Z`` /
    ``+00:00`` — a tz-aware value is converted to local time then made naive so
    it can be compared against ``datetime.now()`` without an aware/naive error.
    """
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _relative_time(iso_str: str) -> str:
    """Convert ISO datetime string to relative time."""
    if not iso_str:
        return ""
    dt = _parse_dt(iso_str)
    if dt is None:
        return iso_str

    now = datetime.now()
    diff = now - dt

    if diff.total_seconds() < 0:
        diff = -diff
        if diff.days > 6:
            return dt.strftime("%b %d")
        elif diff.days > 1:
            return f"in {diff.days} days"
        elif diff.days == 1:
            return "tomorrow"
        elif diff.seconds > 3600:
            return f"in {diff.seconds // 3600}h"
        else:
            return f"in {diff.seconds // 60}m"
    else:
        if diff.days > 30:
            return dt.strftime("%b %d")
        elif diff.days > 6:
            return f"{diff.days // 7}w ago"
        elif diff.days > 1:
            return f"{diff.days}d ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"


def _format_time(iso_str: str) -> str:
    """Format time as h:mm AM/PM."""
    if not iso_str:
        return ""
    dt = _parse_dt(iso_str)
    if dt is None:
        return iso_str
    return dt.strftime("%-I:%M %p")


def _dash(v):
    """Render NULL / empty as an em dash — never a fabricated value."""
    if v is None:
        return "—"
    if isinstance(v, str) and v.strip() == "":
        return "—"
    return v


def _get_nav_context(active_page: str = "dashboard", active_section: str = "",
                     active_entity_id: int = None, tip_text: str = None) -> dict:
    """Build sidebar navigation context for templates (ported from views.py)."""
    modules = get_installed_modules()

    counts = {}
    try:
        for row in execute("""
            SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
            UNION ALL SELECT 'emails', COUNT(*) FROM emails
            UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
        """):
            counts[row["section"]] = row["count"]
    except Exception:
        pass

    urgent = 0
    try:
        row = execute("""
            SELECT
              (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
              + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
              + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
              as urgent_count
        """)
        if row:
            urgent = row[0]["urgent_count"] or 0
    except Exception:
        pass
    counts["urgent"] = urgent

    contact_pages = []
    try:
        contact_pages = execute("""
            SELECT entity_id, entity_name, filename FROM generated_views
            WHERE view_type = 'entity_page' AND entity_type = 'contact'
            ORDER BY entity_name ASC
        """)
    except Exception:
        pass

    project_pages = []
    try:
        project_pages = execute("""
            SELECT entity_id, entity_name, filename FROM generated_views
            WHERE view_type = 'entity_page' AND entity_type = 'project'
            ORDER BY entity_name ASC
        """)
    except Exception:
        pass

    return {
        "modules": modules,
        "active_page": active_page,
        "active_section": active_section,
        "active_entity_id": active_entity_id,
        "nav_counts": type("Counts", (), counts)(),
        "contact_pages": contact_pages,
        "project_pages": project_pages,
        "tip_text": tip_text or "Use /help-soy to see all available commands.",
        "generated_at": datetime.now().strftime("%B %d, %Y at %-I:%M %p"),
    }


def _register(view_type, entity_type, entity_id, entity_name, filename):
    """Upsert a generated_views row keyed by unique filename."""
    execute_many([(
        """INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(filename) DO UPDATE SET entity_name = excluded.entity_name, updated_at = datetime('now')""",
        (view_type, entity_type, entity_id, entity_name, filename),
    )])


def _write(filename: str, html: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / filename).write_text(html)


# =============================================================================
# Slug backfill + entity-page pre-registration
# =============================================================================

def backfill_slugs() -> list[dict]:
    """Ensure every active contact has a stored slug. Returns [{id,name,slug}].

    Slugs are computed once and persisted so a later rename never changes the
    filename. Collisions on the UNIQUE generated_views.filename are extremely
    unlikely for real name sets; if two slugs collide the second simply reuses
    the same file — acceptable for this data, not worth special-casing.
    """
    rows = rows_to_dicts(execute(
        "SELECT id, name, slug FROM contacts WHERE status = 'active' ORDER BY name"
    ))
    out = []
    for c in rows:
        slug = c["slug"]
        if not slug:
            slug = _safe_slug(c["name"], "contact")
            execute_write("UPDATE contacts SET slug = ? WHERE id = ?", (slug, c["id"]))
        out.append({"id": c["id"], "name": c["name"], "slug": slug})
    return out


def preregister_entities(contacts: list[dict]):
    """Upsert generated_views rows for all active contacts BEFORE rendering.

    So every page's sidebar is complete and every contact link resolves on a
    single ``all`` run (the table would otherwise start empty).
    """
    stmts = []
    for c in contacts:
        stmts.append((
            """INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
               VALUES ('entity_page', 'contact', ?, ?, ?)
               ON CONFLICT(filename) DO UPDATE SET entity_name = excluded.entity_name, updated_at = datetime('now')""",
            (c["id"], c["name"], f"contact-{c['slug']}.html"),
        ))
    if stmts:
        execute_many(stmts)


def _contact_has_page(contact_id: int) -> str | None:
    rows = execute(
        "SELECT filename FROM generated_views WHERE entity_type = 'contact' AND entity_id = ?",
        (contact_id,),
    )
    return rows[0]["filename"] if rows else None


# =============================================================================
# Builder: dashboard (ported from views._render_dashboard, writes to output/)
# =============================================================================

def build_dashboard() -> str:
    env = _get_env()
    template = env.get_template("pages/dashboard.html")
    modules = get_installed_modules()
    today = date.today()

    ctx = _get_nav_context("dashboard")

    stats = {"contacts": execute("SELECT COUNT(*) as n FROM contacts")[0]["n"]}
    if "project-tracker" in modules:
        stats["projects"] = execute("SELECT COUNT(*) as n FROM projects WHERE status IN ('active','planning')")[0]["n"]
    if "gmail" in modules:
        stats["unread"] = execute("SELECT COUNT(*) as n FROM emails WHERE is_read = 0")[0]["n"]
    if "calendar" in modules:
        stats["today_events"] = execute("SELECT COUNT(*) as n FROM calendar_events WHERE date(start_time) = date('now') AND status != 'cancelled'")[0]["n"]

    ctx["stats"] = stats
    ctx["today_formatted"] = today.strftime("%A, %B %d, %Y")

    urgent = 0
    try:
        row = execute("""SELECT
            (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
            + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
            + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
            as urgent_count""")
        urgent = row[0]["urgent_count"] if row else 0
    except Exception:
        pass
    ctx["urgent_count"] = urgent

    if "calendar" in modules:
        now = datetime.now()
        today_events_raw = rows_to_dicts(execute(
            "SELECT * FROM calendar_events WHERE date(start_time) = date('now') AND status != 'cancelled' ORDER BY start_time ASC"
        ))
        for e in today_events_raw:
            e["start_formatted"] = _format_time(e["start_time"])
            try:
                start = datetime.fromisoformat(e["start_time"])
                end = datetime.fromisoformat(e["end_time"])
                mins = int((end - start).total_seconds() / 60)
                e["duration"] = f"{mins}m" if mins < 60 else f"{mins // 60}h{mins % 60:02d}m"
                e["is_past"] = end < now
                e["is_next"] = not e["is_past"] and start > now
            except (ValueError, TypeError):
                e["duration"] = ""
                e["is_past"] = False
                e["is_next"] = False
            e["context_line"] = e.get("location", "")

        found_next = False
        for e in today_events_raw:
            if e["is_next"] and not found_next:
                found_next = True
            elif e["is_next"]:
                e["is_next"] = False
        ctx["today_events"] = today_events_raw

        tomorrow_raw = rows_to_dicts(execute(
            "SELECT * FROM calendar_events WHERE date(start_time) = date('now', '+1 day') AND status != 'cancelled' ORDER BY start_time ASC"
        ))
        for e in tomorrow_raw:
            e["start_formatted"] = _format_time(e["start_time"])
        ctx["tomorrow_events"] = tomorrow_raw

    if "gmail" in modules:
        ctx["unread_count"] = stats.get("unread", 0)

        needs_resp = rows_to_dicts(execute(
            """SELECT e.thread_id, e.subject, e.from_name, e.received_at, c.name as contact_name
               FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
               WHERE e.direction = 'inbound'
                 AND e.thread_id NOT IN (SELECT thread_id FROM emails WHERE direction = 'outbound' AND received_at > e.received_at)
                 AND e.received_at > datetime('now', '-7 days')
               GROUP BY e.thread_id ORDER BY e.received_at DESC LIMIT 5"""
        ))
        for t in needs_resp:
            t["received_at_relative"] = _relative_time(t["received_at"])
        ctx["needs_response"] = needs_resp

        recent = rows_to_dicts(execute(
            """SELECT e.thread_id, e.subject, e.snippet, e.from_name, e.direction,
                      e.received_at, e.is_read, e.is_starred, c.name as contact_name
               FROM emails e LEFT JOIN contacts c ON e.contact_id = c.id
               WHERE e.id IN (SELECT MAX(id) FROM emails GROUP BY thread_id)
               ORDER BY e.received_at DESC LIMIT 8"""
        ))
        for t in recent:
            t["received_at_relative"] = _relative_time(t["received_at"])
        ctx["recent_threads"] = recent

    if "project-tracker" in modules:
        ctx["active_projects"] = rows_to_dicts(execute(
            """SELECT p.id, p.name, p.status, p.priority, c.name as client_name
               FROM projects p LEFT JOIN contacts c ON p.client_id = c.id
               WHERE p.status IN ('active', 'planning') ORDER BY p.priority DESC LIMIT 8"""
        ))
        task_rows = execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
        ctx["task_stats"] = {r["status"]: r["count"] for r in task_rows}
        ctx["overdue_tasks"] = rows_to_dicts(execute(
            """SELECT t.title, t.due_date, p.name as project_name FROM tasks t
               JOIN projects p ON p.id = t.project_id
               WHERE t.due_date < date('now') AND t.status NOT IN ('done') LIMIT 5"""
        ))

    contacts_raw = rows_to_dicts(execute(
        "SELECT id, name, company, role, email, updated_at FROM contacts WHERE status = 'active' ORDER BY updated_at DESC LIMIT 8"
    ))
    for c in contacts_raw:
        c["entity_page"] = _contact_has_page(c["id"])
    ctx["recent_contacts"] = contacts_raw

    if "crm" in modules:
        fus = rows_to_dicts(execute(
            """SELECT f.*, c.name as contact_name FROM follow_ups f
               JOIN contacts c ON c.id = f.contact_id
               WHERE f.status = 'pending' ORDER BY f.due_date ASC LIMIT 8"""
        ))
        today_str = today.isoformat()
        for fu in fus:
            fu["overdue"] = fu["due_date"] < today_str
            fu["due_today"] = fu["due_date"] == today_str
            fu["due_date_relative"] = _relative_time(fu["due_date"] + "T12:00:00")
        ctx["follow_ups"] = fus

    activity_raw = rows_to_dicts(execute(
        """SELECT al.*, CASE al.entity_type
               WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
               WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
               ELSE al.entity_type || ' #' || al.entity_id
             END as entity_name
           FROM activity_log al ORDER BY al.created_at DESC LIMIT 15"""
    ))
    icon_map = {"created": "plus", "updated": "edit-3", "interaction_logged": "message-circle",
                "follow_up_created": "clock", "follow_up_completed": "check-circle",
                "imported": "upload", "task_added": "plus-square", "task_updated": "check-square"}
    for a in activity_raw:
        a["icon"] = icon_map.get(a["action"], "activity")
        a["created_at_relative"] = _relative_time(a["created_at"])
    ctx["activity"] = activity_raw

    from software_of_you.db import DATA_DIR
    ctx["google_connected"] = (DATA_DIR / "google_token.json").exists() or (DATA_DIR / "tokens").is_dir()

    html = template.render(**ctx)
    _write("dashboard.html", html)
    _register("dashboard", None, None, "Dashboard", "dashboard.html")
    return "dashboard.html"


# =============================================================================
# Builder: entity pages (ported from views._render_entity_page)
# =============================================================================

def build_entity_page(contact_id: int, slug: str) -> str:
    rows = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    if not rows:
        raise ValueError(f"No contact with id {contact_id}")
    contact = rows_to_dicts(rows)[0]
    modules = get_installed_modules()

    ctx = _get_nav_context("contacts", "people", active_entity_id=contact_id,
                           tip_text="Use /follow-up to set a reminder for this person.")
    ctx["contact"] = contact

    ctx["tags"] = rows_to_dicts(execute(
        "SELECT t.name, t.color FROM tags t JOIN entity_tags et ON et.tag_id = t.id WHERE et.entity_type = 'contact' AND et.entity_id = ?",
        (contact_id,),
    ))

    ctx["notes"] = rows_to_dicts(execute(
        "SELECT content, created_at FROM notes WHERE entity_type = 'contact' AND entity_id = ? ORDER BY created_at DESC LIMIT 5",
        (contact_id,),
    ))

    if "gmail" in modules:
        emails_raw = rows_to_dicts(execute(
            "SELECT * FROM emails WHERE contact_id = ? ORDER BY received_at ASC", (contact_id,),
        ))
        for e in emails_raw:
            e["received_at_formatted"] = _relative_time(e["received_at"])
        ctx["emails"] = emails_raw

    if "calendar" in modules:
        events_raw = rows_to_dicts(execute(
            "SELECT * FROM calendar_events WHERE contact_ids LIKE ? AND status != 'cancelled' AND start_time > datetime('now') ORDER BY start_time ASC LIMIT 5",
            (f"%{contact_id}%",),
        ))
        for e in events_raw:
            e["start_formatted"] = _format_time(e["start_time"]) + " · " + _relative_time(e["start_time"])
        ctx["upcoming_events"] = events_raw

    if "project-tracker" in modules:
        projects = rows_to_dicts(execute(
            "SELECT * FROM projects WHERE client_id = ?", (contact_id,),
        ))
        for p in projects:
            p["tasks"] = rows_to_dicts(execute(
                "SELECT title, status FROM tasks WHERE project_id = ? ORDER BY sort_order", (p["id"],),
            ))
        ctx["projects"] = projects

    if "crm" in modules:
        fus = rows_to_dicts(execute(
            "SELECT * FROM follow_ups WHERE contact_id = ? AND status = 'pending' ORDER BY due_date ASC",
            (contact_id,),
        ))
        today_str = date.today().isoformat()
        for fu in fus:
            fu["overdue"] = fu["due_date"] < today_str
        ctx["follow_ups"] = fus

    if "conversation-intelligence" in modules:
        transcripts = rows_to_dicts(execute(
            """SELECT t.id, t.title, t.summary, t.call_intelligence, t.occurred_at
               FROM transcripts t
               JOIN transcript_participants tp ON tp.transcript_id = t.id
               WHERE tp.contact_id = ?
               GROUP BY t.id ORDER BY t.occurred_at DESC LIMIT 10""",
            (contact_id,),
        ))
        ctx["transcripts"] = transcripts

        ci_agg = {"pain_points": [], "tech_stack": [], "key_concerns": []}
        seen_pp = set()
        seen_ts = set()
        for t in transcripts:
            if t.get("call_intelligence"):
                try:
                    ci = json.loads(t["call_intelligence"]) if isinstance(t["call_intelligence"], str) else t["call_intelligence"]
                    for pp in ci.get("pain_points", []):
                        if pp.get("title") not in seen_pp:
                            seen_pp.add(pp["title"])
                            ci_agg["pain_points"].append(pp)
                    for ts in ci.get("tech_stack", []):
                        if ts.get("name") not in seen_ts:
                            seen_ts.add(ts["name"])
                            ci_agg["tech_stack"].append(ts)
                    for kc in ci.get("key_concerns", []):
                        ci_agg["key_concerns"].append(kc)
                except (json.JSONDecodeError, TypeError):
                    pass
        if any(ci_agg.values()):
            ctx["call_intelligence"] = ci_agg

        rs = rows_to_dicts(execute(
            "SELECT * FROM relationship_scores WHERE contact_id = ? ORDER BY score_date DESC LIMIT 1",
            (contact_id,),
        ))
        ctx["relationship_score"] = rs[0] if rs else None

    if "notes" in modules:
        sn = rows_to_dicts(execute(
            "SELECT id, title, substr(content, 1, 150) as preview, tags, pinned FROM standalone_notes WHERE linked_contacts LIKE ? ORDER BY pinned DESC LIMIT 5",
            (f"%{contact_id}%",),
        ))
        for n in sn:
            if n.get("tags"):
                try:
                    n["tags"] = json.loads(n["tags"]) if isinstance(n["tags"], str) else n["tags"]
                except (json.JSONDecodeError, TypeError):
                    n["tags"] = []
        ctx["standalone_notes"] = sn

    if contact.get("company"):
        team = rows_to_dicts(execute(
            "SELECT name, role FROM contacts WHERE company = ? AND id != ? AND status = 'active'",
            (contact["company"], contact_id),
        ))
        ctx["company_team"] = team

    # Narrative sections sourced from the DB (not a Claude argument).
    ns = {}
    next_action = None
    nar = execute("SELECT * FROM entity_narratives WHERE contact_id = ?", (contact_id,))
    if nar:
        r = dict(nar[0])
        if r.get("relationship_context"):
            ns["relationship_context"] = r["relationship_context"]
        if r.get("company_intel"):
            ns["company_intel"] = r["company_intel"]
        if r.get("next_action"):
            next_action = r["next_action"]
        dq = r.get("discovery_questions")
        if dq:
            try:
                arr = json.loads(dq) if isinstance(dq, str) else dq
            except (json.JSONDecodeError, TypeError):
                arr = None
            if arr:
                # Trusted-markup channel: each question is html-escaped before
                # concatenation (the sanctioned pattern from views.py's audit
                # note), so no unescaped DB text can reach the browser. This is
                # the only way to get list rendering without editing the template.
                items = "".join(f"<li>{escape(q)}</li>" for q in arr)
                ns["discovery_questions"] = Markup(
                    f'<ul class="list-disc pl-5 space-y-1">{items}</ul>'
                )
    ctx["narrative_sections"] = ns
    ctx["next_action"] = next_action

    env = _get_env()
    template = env.get_template("pages/entity_page.html")
    html = template.render(**ctx)
    filename = f"contact-{slug}.html"
    _write(filename, html)
    _register("entity_page", "contact", contact_id, contact["name"], filename)
    return filename


# =============================================================================
# Generic module_view builder
# =============================================================================

def build_module_view(filename, page_title, active_page, active_section,
                      header_stats, sections, page_subtitle="",
                      entity_name=None) -> str:
    ctx = _get_nav_context(active_page, active_section)
    ctx["page_title"] = page_title
    ctx["page_subtitle"] = page_subtitle
    ctx["header_stats"] = header_stats
    # Sections must be objects, not dicts: the template reads ``section.items``
    # (list sections), and Jinja's getattr-first precedence would resolve that
    # to the dict's built-in ``.items()`` method instead of our list. Attribute
    # access on a SimpleNamespace returns the value; missing attrs fall through
    # to Jinja's Undefined (so ``| default(...)`` and ``{% if %}`` still work).
    ctx["sections"] = [SimpleNamespace(**s) for s in sections]

    env = _get_env()
    template = env.get_template("pages/module_view.html")
    html = template.render(**ctx)
    _write(filename, html)
    _register("module_view", "module", None, entity_name or page_title, filename)
    return filename


def _empty_section(title, icon, message, hint=""):
    return {"type": "empty", "title": title, "icon": icon,
            "empty_icon": icon, "empty_message": message, "empty_hint": hint}


# =============================================================================
# Module view: contacts.html
# =============================================================================

def build_contacts() -> str:
    rows = rows_to_dicts(execute("""
        SELECT id, name, company, days_silent, relationship_depth,
               your_open_commitments, their_open_commitments, next_meeting
        FROM v_contact_health WHERE status = 'active'
        ORDER BY (days_silent IS NULL), days_silent DESC, name
    """))

    if not rows:
        sections = [_empty_section("Contacts", "users", "No active contacts yet",
                                   "Add someone to start tracking relationships")]
        return build_module_view("contacts.html", "Contacts", "contacts", "people",
                                 [], sections, "Active relationships at a glance")

    # Build a linkable table as a trusted type:'html' section. Every DB value is
    # escape()'d; only the whitelisted slug goes into the href.
    columns = ["Name", "Company", "Days silent", "Depth", "Open commitments", "Next meeting"]
    header = "".join(
        f'<th class="text-{"right" if i == len(columns) - 1 else "left"} py-2 text-zinc-500 font-medium">{escape(c)}</th>'
        for i, c in enumerate(columns)
    )
    body_rows = []
    for c in rows:
        filename = _contact_has_page(c["id"])
        name_esc = escape(c["name"])
        if filename:
            name_cell = f'<a href="{escape(filename)}" class="text-blue-600 hover:text-blue-800 hover:underline">{name_esc}</a>'
        else:
            name_cell = str(name_esc)
        open_c = (c.get("your_open_commitments") or 0) + (c.get("their_open_commitments") or 0)
        cells = [
            (name_cell, "font-medium"),
            (str(escape(_dash(c.get("company")))), ""),
            (str(escape(str(_dash(c.get("days_silent"))))), ""),
            (str(escape(str(_dash(c.get("relationship_depth") and str(c["relationship_depth"]).title())))), ""),
            (str(open_c), ""),
            (str(escape(_relative_time(c["next_meeting"]) if c.get("next_meeting") else "—")), "text-right text-zinc-500"),
        ]
        tds = "".join(f'<td class="py-2.5 {cls}">{val}</td>' for val, cls in cells)
        body_rows.append(f'<tr class="border-b border-zinc-50 hover:bg-zinc-50">{tds}</tr>')

    table_html = Markup(
        '<table class="w-full text-sm"><thead><tr class="border-b border-zinc-100">'
        + header + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table>"
    )
    sections = [{
        "type": "html",
        "title": "Active Contacts",
        "icon": "users",
        "badge": str(len(rows)),
        "badge_color": "blue",
        "html": table_html,
    }]
    return build_module_view("contacts.html", "Contacts", "contacts", "people",
                             [{"label": "Active", "value": len(rows), "color": "blue"}],
                             sections, "Active relationships at a glance")


# =============================================================================
# Module view: nudges.html
# =============================================================================

_TIER_META = {
    "urgent": ("red", "alert-triangle", "Urgent"),
    "soon": ("amber", "clock", "Soon"),
    "awareness": ("blue", "eye", "Awareness"),
}
_TIER_ORDER = ["urgent", "soon", "awareness"]


def build_nudges() -> str:
    summary = {r["tier"]: r["count"] for r in execute("SELECT tier, count FROM v_nudge_summary")}
    items = rows_to_dicts(execute("""
        SELECT nudge_type, tier, entity_name, description, relevant_date,
               days_value, extra_context, icon
        FROM v_nudge_items
    """))

    by_tier = {}
    for it in items:
        by_tier.setdefault(it["tier"], []).append(it)

    header_stats = []
    for tier in _TIER_ORDER:
        if tier in summary:
            color, _, label = _TIER_META[tier]
            header_stats.append({"label": label, "value": summary[tier], "color": color})

    sections = []
    for tier in _TIER_ORDER:
        rows = by_tier.get(tier)
        if not rows:
            continue
        color, icon, label = _TIER_META[tier]
        table_rows = []
        for it in rows:
            when = _relative_time(it["relevant_date"]) if it.get("relevant_date") else (
                f"{it['days_value']}d" if it.get("days_value") is not None else "—")
            who = _dash(it.get("entity_name"))
            ctx_line = it.get("extra_context") or it.get("nudge_type") or ""
            table_rows.append([it.get("description") or "—", who, ctx_line, when])
        sections.append({
            "type": "table",
            "title": label,
            "icon": icon,
            "badge": str(len(rows)),
            "badge_color": color,
            "columns": ["What", "Who", "Context", "When"],
            "rows": table_rows,
        })

    if not sections:
        sections = [_empty_section("Nudges", "bell", "Nothing needs attention",
                                   "You're all caught up")]

    return build_module_view("nudges.html", "Nudges", "nudges", "tools",
                             header_stats, sections, "Everything that needs your attention")


# =============================================================================
# Module view: week-view.html
# =============================================================================

def build_week_view() -> str:
    events = rows_to_dicts(execute("""
        SELECT title, location, start_time, end_time
        FROM calendar_events
        WHERE start_time BETWEEN datetime('now') AND datetime('now', '+7 days')
          AND status != 'cancelled'
        ORDER BY start_time ASC
    """))

    by_day = {}
    order = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e["start_time"])
            key = dt.strftime("%A, %b %-d")
        except (ValueError, TypeError):
            key = "Undated"
        if key not in by_day:
            by_day[key] = []
            order.append(key)
        span = _format_time(e["start_time"])
        if e.get("end_time"):
            span += " – " + _format_time(e["end_time"])
        by_day[key].append({
            "avatar": None,
            "title": e["title"],
            "subtitle": _dash(e.get("location")) if e.get("location") else "",
            "meta": span,
        })

    sections = []
    for key in order:
        sections.append({
            "type": "list",
            "title": key,
            "icon": "calendar",
            "badge": str(len(by_day[key])),
            "badge_color": "emerald",
            "items": by_day[key],
        })

    if not sections:
        sections = [_empty_section("This Week", "calendar-off", "No meetings in the next 7 days", "")]

    return build_module_view("week-view.html", "This Week", "calendar", "comms",
                             [{"label": "Events", "value": len(events), "color": "emerald"}],
                             sections, "Your next 7 days")


# =============================================================================
# Module view: email-hub.html
# =============================================================================

_AUTOMATION_LOCALPARTS = {
    "notifications", "noreply", "no-reply", "donotreply",
    "mailer-daemon", "postmaster", "bounce",
}


def _is_automation(from_name: str, from_address: str) -> bool:
    name = (from_name or "").lower()
    if "[bot]" in name:
        return True
    addr = (from_address or "").lower()
    localpart = addr.split("@", 1)[0] if "@" in addr else addr
    if localpart in _AUTOMATION_LOCALPARTS:
        return True
    if "noreply" in localpart:
        return True
    return False


def build_email_hub() -> str:
    queue = rows_to_dicts(execute("""
        SELECT subject, from_name, from_address, contact_name, days_old, urgency
        FROM v_email_response_queue
        ORDER BY days_old DESC
    """))
    needs = [q for q in queue if not _is_automation(q.get("from_name"), q.get("from_address"))]

    items = []
    for q in needs:
        who = q.get("contact_name") or q.get("from_name") or q.get("from_address") or "?"
        initials = "".join(w[0] for w in str(who).split()[:2]).upper() or "?"
        age = f"{q['days_old']}d old" if q.get("days_old") is not None else ""
        meta = age
        if q.get("urgency"):
            meta = f"{q['urgency']} · {age}" if age else str(q["urgency"])
        items.append({
            "avatar": initials,
            "avatar_color": "amber",
            "title": who,
            "subtitle": _dash(q.get("subject")),
            "meta": meta,
        })

    sections = []
    if items:
        sections.append({
            "type": "list",
            "title": "Needs Response",
            "icon": "reply",
            "badge": str(len(items)),
            "badge_color": "amber",
            "items": items,
        })
    else:
        sections.append(_empty_section("Needs Response", "mail-check",
                                       "Nothing awaiting a reply", "Inbox is under control"))

    recent = rows_to_dicts(execute("""
        SELECT e.from_name, e.from_address, e.subject, e.received_at
        FROM emails e
        WHERE e.id IN (SELECT MAX(id) FROM emails GROUP BY thread_id)
        ORDER BY e.received_at DESC LIMIT 40
    """))
    recent_rows = []
    for r in recent:
        sender = r.get("from_name") or r.get("from_address") or "—"
        recent_rows.append([sender, _dash(r.get("subject")), _relative_time(r["received_at"])])
    if recent_rows:
        sections.append({
            "type": "table",
            "title": "Recent Threads",
            "icon": "mail",
            "badge": str(len(recent_rows)),
            "badge_color": "zinc",
            "columns": ["From", "Subject", "When"],
            "rows": recent_rows,
        })

    return build_module_view("email-hub.html", "Email", "email", "comms",
                             [{"label": "Needs reply", "value": len(items), "color": "amber"}],
                             sections, "Inbound threads and what needs a reply")


# =============================================================================
# Module view: timeline.html
# =============================================================================

def build_timeline() -> str:
    rows = rows_to_dicts(execute("""
        SELECT al.action, al.details, al.entity_type, al.entity_id, al.created_at,
               CASE al.entity_type
                   WHEN 'contact' THEN (SELECT name FROM contacts WHERE id = al.entity_id)
                   WHEN 'project' THEN (SELECT name FROM projects WHERE id = al.entity_id)
                   ELSE al.entity_type || ' #' || al.entity_id
               END as entity_name
        FROM activity_log al ORDER BY al.created_at DESC LIMIT 50
    """))

    icon_map = {"created": "plus", "updated": "edit-3", "interaction_logged": "message-circle",
                "follow_up_created": "clock", "follow_up_completed": "check-circle",
                "imported": "upload", "task_added": "plus-square", "task_updated": "check-square"}

    entries = []
    for a in rows:
        action = str(a["action"] or "").replace("_", " ").title()
        name = a.get("entity_name") or ""
        content = f"{action} {name}".strip()
        if a.get("details"):
            content += f" — {a['details']}"
        entries.append({
            "icon": icon_map.get(a["action"], "activity"),
            "color": "purple",
            "content": content,
            "time": _relative_time(a["created_at"]),
        })

    if entries:
        sections = [{"type": "timeline", "title": "Recent Activity", "icon": "clock", "entries": entries}]
    else:
        sections = [_empty_section("Timeline", "clock", "No activity logged yet",
                                   "Actions across everything will appear here")]

    return build_module_view("timeline.html", "Timeline", "timeline", "tools",
                             [{"label": "Events", "value": len(entries), "color": "purple"}],
                             sections, "Activity across everything")


# =============================================================================
# Module view: conversations.html
# =============================================================================

def build_conversations() -> str:
    rows = rows_to_dicts(execute("""
        SELECT title, occurred_at, duration_minutes, processed_at
        FROM transcripts ORDER BY occurred_at DESC
    """))

    table_rows = []
    analyzed_count = 0
    for r in rows:
        analyzed = bool(r.get("processed_at"))
        if analyzed:
            analyzed_count += 1
        dur = f"{r['duration_minutes']}m" if r.get("duration_minutes") is not None else "—"
        table_rows.append([
            _dash(r.get("title")),
            _relative_time(r["occurred_at"]) if r.get("occurred_at") else "—",
            dur,
            "Analyzed" if analyzed else "Pending",
        ])

    if table_rows:
        sections = [{
            "type": "table",
            "title": "Meeting Transcripts",
            "icon": "message-square",
            "badge": f"{analyzed_count}/{len(rows)} analyzed",
            "badge_color": "violet",
            "columns": ["Title", "When", "Duration", "Status"],
            "rows": table_rows,
        }]
    else:
        sections = [_empty_section("Conversations", "message-square",
                                   "No transcripts yet", "Upload a call transcript to get started")]

    return build_module_view("conversations.html", "Conversations", "conversations", "intelligence",
                             [{"label": "Transcripts", "value": len(rows), "color": "violet"}],
                             sections, "Every meeting transcript on file")


# =============================================================================
# Module view: weekly-review.html
# =============================================================================

def build_weekly_review() -> str:
    meetings = rows_to_dicts(execute("""
        SELECT title, start_time FROM calendar_events
        WHERE start_time BETWEEN datetime('now', '-7 days') AND datetime('now')
          AND status != 'cancelled'
        ORDER BY start_time DESC
    """))
    made = rows_to_dicts(execute("""
        SELECT description, created_at FROM commitments
        WHERE created_at >= datetime('now', '-7 days')
        ORDER BY created_at DESC
    """))
    closed_count = execute("""
        SELECT COUNT(*) as n FROM commitments
        WHERE status = 'completed' AND completed_at >= datetime('now', '-7 days')
    """)[0]["n"]
    touched = rows_to_dicts(execute("""
        SELECT DISTINCT c.name FROM emails e JOIN contacts c ON c.id = e.contact_id
        WHERE e.received_at >= datetime('now', '-7 days') AND e.contact_id IS NOT NULL
        ORDER BY c.name
    """))

    stats = [
        {"value": len(meetings), "label": "Meetings held"},
        {"value": len(made), "label": "Commitments made"},
        {"value": closed_count, "label": "Commitments closed"},
        {"value": len(touched), "label": "Contacts touched"},
    ]
    sections = [{"type": "stats", "title": "Last 7 Days", "stats": stats}]

    if meetings:
        sections.append({
            "type": "list",
            "title": "Meetings Held",
            "icon": "calendar",
            "badge": str(len(meetings)),
            "badge_color": "blue",
            "items": [{"avatar": None, "title": m["title"],
                       "subtitle": "", "meta": _relative_time(m["start_time"])} for m in meetings],
        })
    if made:
        sections.append({
            "type": "list",
            "title": "Commitments Made",
            "icon": "flag",
            "badge": str(len(made)),
            "badge_color": "amber",
            "items": [{"avatar": None, "title": c["description"],
                       "subtitle": "", "meta": _relative_time(c["created_at"])} for c in made],
        })
    if touched:
        sections.append({
            "type": "list",
            "title": "Contacts Touched",
            "icon": "users",
            "badge": str(len(touched)),
            "badge_color": "emerald",
            "items": [{"avatar": None, "title": t["name"], "subtitle": "", "meta": ""} for t in touched],
        })

    return build_module_view("weekly-review.html", "Weekly Review", "weekly-review", "tools",
                             [{"label": "Meetings", "value": len(meetings), "color": "blue"}],
                             sections, "Your last 7 days, summarized")


# =============================================================================
# Module view: network-map.html (simple: contacts grouped by company)
# =============================================================================

def build_network_map() -> str:
    rows = rows_to_dicts(execute("""
        SELECT id, name, company, role FROM contacts
        WHERE status = 'active'
        ORDER BY (company IS NULL OR company = ''), company, name
    """))

    by_company = {}
    order = []
    for c in rows:
        key = c["company"] if (c.get("company") and c["company"].strip()) else "Independent / No company"
        if key not in by_company:
            by_company[key] = []
            order.append(key)
        initials = "".join(w[0] for w in str(c["name"]).split()[:2]).upper() or "?"
        by_company[key].append({
            "avatar": initials,
            "avatar_color": "blue",
            "title": c["name"],
            "subtitle": _dash(c.get("role")) if c.get("role") else "",
            "meta": "",
        })

    sections = []
    for key in order:
        members = by_company[key]
        sections.append({
            "type": "list",
            "title": key,
            "icon": "building-2",
            "badge": str(len(members)),
            "badge_color": "blue",
            "items": members,
        })

    if not sections:
        sections = [_empty_section("Network", "share-2", "No contacts to map yet", "")]

    company_count = len([k for k in order if k != "Independent / No company"])
    return build_module_view("network-map.html", "Network Map", "network", "people",
                             [{"label": "Companies", "value": company_count, "color": "blue"},
                              {"label": "Contacts", "value": len(rows), "color": "zinc"}],
                             sections, "Your network grouped by company")


# =============================================================================
# Module view: search.html (simple client-side filter over contacts + projects)
# =============================================================================

def build_search() -> str:
    modules = get_installed_modules()
    index = []

    contacts = rows_to_dicts(execute(
        "SELECT id, name FROM contacts WHERE status = 'active' ORDER BY name"))
    for c in contacts:
        href = _contact_has_page(c["id"]) or ""
        index.append({"name": c["name"], "type": "contact", "href": href})

    if "project-tracker" in modules:
        projects = rows_to_dicts(execute("SELECT id, name FROM projects ORDER BY name"))
        for p in projects:
            rows = execute(
                "SELECT filename FROM generated_views WHERE entity_type = 'project' AND entity_id = ?",
                (p["id"],))
            href = rows[0]["filename"] if rows else ""
            index.append({"name": p["name"], "type": "project", "href": href})

    # json.dumps does NOT escape <>&; harden against a name that closes the
    # <script> tag before embedding. Names are re-rendered client-side via
    # textContent (never innerHTML), so the browser treats them as inert text.
    payload = (
        json.dumps(index)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    search_html = Markup("""
<div>
  <input id="soy-search" type="text" placeholder="Search contacts and projects…" autocomplete="off"
         class="w-full px-4 py-2 rounded-lg border border-zinc-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 mb-4">
  <ul id="soy-results" class="space-y-1"></ul>
</div>
<script>
(function () {
  var ITEMS = __PAYLOAD__;
  var box = document.getElementById('soy-search');
  var out = document.getElementById('soy-results');
  var TYPE_COLOR = { contact: '#eff6ff', project: '#f5f3ff' };
  function render(q) {
    q = (q || '').toLowerCase();
    out.innerHTML = '';
    var matches = ITEMS.filter(function (it) { return it.name.toLowerCase().indexOf(q) !== -1; });
    matches.slice(0, 100).forEach(function (it) {
      var li = document.createElement('li');
      li.className = 'flex items-center gap-2 py-2 border-b border-zinc-50 text-sm';
      var badge = document.createElement('span');
      badge.className = 'px-2 py-0.5 rounded-full text-xs text-zinc-600';
      badge.style.background = TYPE_COLOR[it.type] || '#f4f4f5';
      badge.textContent = it.type;
      var label;
      if (it.href) {
        label = document.createElement('a');
        label.href = it.href;
        label.className = 'text-blue-600 hover:underline';
      } else {
        label = document.createElement('span');
        label.className = 'text-zinc-800';
      }
      label.textContent = it.name;
      li.appendChild(badge);
      li.appendChild(label);
      out.appendChild(li);
    });
    if (matches.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'text-sm text-zinc-400 py-2';
      empty.textContent = 'No matches';
      out.appendChild(empty);
    }
  }
  box.addEventListener('input', function () { render(box.value); });
  render('');
})();
</script>
""".replace("__PAYLOAD__", payload))

    sections = [{"type": "html", "title": None, "html": search_html}]
    return build_module_view("search.html", "Search", "search", "tools",
                             [{"label": "Indexed", "value": len(index), "color": "emerald"}],
                             sections, "Find any contact or project")


# =============================================================================
# Stale-narrative detection (report only)
# =============================================================================

def _fingerprint(row: dict) -> str:
    payload = (
        row.get("emails_total"),
        row.get("interactions_total"),
        row.get("transcripts_total"),
        row.get("last_activity"),
    )
    return hashlib.sha1(repr(payload).encode("utf-8")).hexdigest()[:16]


def _current_fingerprint(contact_id: int) -> str | None:
    rows = rows_to_dicts(execute("""
        SELECT emails_total, interactions_total, transcripts_total, last_activity
        FROM v_contact_health WHERE id = ?""", (contact_id,)))
    return _fingerprint(rows[0]) if rows else None


def save_narrative(payload: dict) -> dict:
    """Upsert a Claude-authored narrative for one contact and re-render its page.

    render.py owns the data_fingerprint so "fresh" is computed identically to the
    staleness check — callers (build-all) just supply the prose; they never guess
    the fingerprint. Expects: {contact_id, relationship_context, company_intel,
    discovery_questions:[...], next_action}. Re-renders that entity page so the
    change is visible immediately.
    """
    cid = payload.get("contact_id")
    if not cid:
        return {"error": "contact_id is required"}
    crow = execute("SELECT slug, name FROM contacts WHERE id = ?", (cid,))
    if not crow:
        return {"error": f"no contact {cid}"}
    slug = crow[0]["slug"] or _safe_slug(crow[0]["name"], "contact")
    if not crow[0]["slug"]:
        execute_write("UPDATE contacts SET slug = ? WHERE id = ?", (slug, cid))

    dq = payload.get("discovery_questions")
    dq_json = json.dumps(dq) if isinstance(dq, (list, tuple)) else (dq or None)
    fp = _current_fingerprint(cid)
    execute_many([(
        """INSERT INTO entity_narratives
           (contact_id, relationship_context, company_intel, discovery_questions,
            next_action, generated_at, data_fingerprint, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
           ON CONFLICT(contact_id) DO UPDATE SET
             relationship_context = excluded.relationship_context,
             company_intel = excluded.company_intel,
             discovery_questions = excluded.discovery_questions,
             next_action = excluded.next_action,
             generated_at = datetime('now'),
             data_fingerprint = excluded.data_fingerprint,
             updated_at = datetime('now')""",
        (cid, payload.get("relationship_context"), payload.get("company_intel"),
         dq_json, payload.get("next_action"), fp),
    )])
    filename = build_entity_page(cid, slug)
    return {"saved": cid, "rendered": filename, "fingerprint": fp}


def stale_narratives() -> list[dict]:
    rows = rows_to_dicts(execute("""
        SELECT ch.id, ch.name, ch.emails_total, ch.interactions_total,
               ch.transcripts_total, ch.last_activity, c.slug,
               n.data_fingerprint, n.generated_at
        FROM v_contact_health ch
        JOIN contacts c ON c.id = ch.id
        LEFT JOIN entity_narratives n ON n.contact_id = ch.id
        WHERE ch.status = 'active'
        ORDER BY ch.name
    """))
    stale = []
    for r in rows:
        worth = (r.get("emails_total") or 0) > 0 or (r.get("transcripts_total") or 0) > 0
        if not worth:
            continue
        current = _fingerprint(r)
        is_stale = (
            r.get("generated_at") is None
            or r.get("data_fingerprint") is None
            or r["data_fingerprint"] != current
        )
        if is_stale:
            slug = r.get("slug") or _safe_slug(r["name"], "contact")
            stale.append({"contact_id": r["id"], "name": r["name"], "slug": slug})
    return stale


# =============================================================================
# Orchestration
# =============================================================================

def _run(built, errors, label, fn):
    try:
        result = fn()
        if isinstance(result, list):
            built.extend(result)
        elif result:
            built.append(result)
    except Exception as e:
        errors.append({"page": label, "error": f"{type(e).__name__}: {e}"})


def _build_entities(built, errors, contacts):
    for c in contacts:
        _run(built, errors, f"contact-{c['slug']}.html",
             lambda c=c: build_entity_page(c["id"], c["slug"]))


_MODULE_BUILDERS = [
    ("contacts.html", build_contacts),
    ("nudges.html", build_nudges),
    ("week-view.html", build_week_view),
    ("email-hub.html", build_email_hub),
    ("timeline.html", build_timeline),
    ("conversations.html", build_conversations),
    ("weekly-review.html", build_weekly_review),
    ("network-map.html", build_network_map),
    ("search.html", build_search),
]


def _build_modules(built, errors):
    for label, fn in _MODULE_BUILDERS:
        _run(built, errors, label, fn)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "all"
    start = time.perf_counter()

    if cmd == "stale-narratives":
        print(json.dumps(stale_narratives(), indent=2))
        return 0

    if cmd == "save-narrative":
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"error": f"invalid JSON on stdin: {e}"}))
            return 2
        result = save_narrative(payload)
        print(json.dumps(result))
        return 0 if "error" not in result else 1

    # Every render path needs stable slugs + pre-registered entity rows so that
    # sidebars are complete and contact links resolve on a single pass.
    contacts = backfill_slugs()
    preregister_entities(contacts)

    built, errors = [], []

    if cmd == "dashboard":
        _run(built, errors, "dashboard.html", build_dashboard)
    elif cmd == "entities":
        _build_entities(built, errors, contacts)
    elif cmd == "modules":
        _build_modules(built, errors)
    elif cmd == "all":
        _build_entities(built, errors, contacts)
        _run(built, errors, "dashboard.html", build_dashboard)
        _build_modules(built, errors)
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}. "
                          "Use: all|dashboard|entities|modules|stale-narratives"}))
        return 2

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    summary = {"built": built, "count": len(built), "ms": elapsed_ms}
    if errors:
        summary["errors"] = errors
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
