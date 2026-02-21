"""View generation tool — render Jinja2 templates to HTML and open in browser.

This replaces the plugin's bespoke HTML generation with consistent,
instant template rendering.
"""

import json
import platform
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import jinja2

from mcp.server.fastmcp import FastMCP

from software_of_you.db import (
    execute, execute_many, rows_to_dicts,
    get_installed_modules, VIEWS_DIR,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _get_env() -> jinja2.Environment:
    """Get Jinja2 environment with template directory."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )


def _relative_time(iso_str: str) -> str:
    """Convert ISO datetime string to relative time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00").replace("+00:00", ""))
    except (ValueError, TypeError):
        return iso_str

    now = datetime.now()
    diff = now - dt

    if diff.total_seconds() < 0:
        # Future
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
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00").replace("+00:00", ""))
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return iso_str


def _get_nav_context(active_page: str = "dashboard", active_group: str = "",
                      breadcrumbs: list = None, sub_nav: list = None) -> dict:
    """Build navigation context for templates."""
    modules = get_installed_modules()

    # Nav counts
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

    return {
        "modules": modules,
        "active_page": active_page,
        "active_group": active_group,
        "nav_counts": type("Counts", (), counts)(),
        "breadcrumbs": breadcrumbs or [],
        "sub_nav": sub_nav or [],
        "generated_at": datetime.now().strftime("%B %d, %Y at %-I:%M %p"),
    }


def _open_file(path: Path) -> None:
    """Open a file in the default browser."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            subprocess.Popen(["start", "", str(path)], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Could not open file: {e}", file=sys.stderr)


def register(server: FastMCP) -> None:
    @server.tool()
    def generate_view(
        view_type: str,
        contact_id: int = 0,
        project_id: int = 0,
        narrative_sections: str = "",
        sections_data: str = "",
        open_after: bool = True,
    ) -> dict:
        """Generate an HTML view from templates and open in browser.

        view_type options:
          dashboard    — Full dashboard with all modules
          entity_page  — Contact profile page (contact_id required)
          module_view  — Generic module view (sections_data as JSON for flexible content)

        For entity pages with narrative sections (two-step flow):
        1. Call get_profile() first to get all data
        2. Write narrative text from the data
        3. Call generate_view with narrative_sections JSON containing:
           - relationship_context: prose about the relationship
           - company_intel: prose about the company
           - discovery_questions: HTML list of questions

        sections_data is a JSON string for module_view, containing:
          page_title, page_subtitle, active_page, active_group,
          breadcrumbs, header_stats, sections (array of section objects)
        """
        if view_type == "dashboard":
            return _render_dashboard(open_after)
        elif view_type == "entity_page":
            return _render_entity_page(contact_id, narrative_sections, open_after)
        elif view_type == "module_view":
            return _render_module_view(sections_data, open_after)
        else:
            return {"error": f"Unknown view_type: {view_type}. Use: dashboard, entity_page, module_view"}


def _render_dashboard(open_after: bool) -> dict:
    env = _get_env()
    template = env.get_template("pages/dashboard.html")
    modules = get_installed_modules()
    today = date.today()

    # Gather all dashboard data
    ctx = _get_nav_context("dashboard")

    # Stats
    stats = {"contacts": execute("SELECT COUNT(*) as n FROM contacts")[0]["n"]}
    if "project-tracker" in modules:
        stats["projects"] = execute("SELECT COUNT(*) as n FROM projects WHERE status IN ('active','planning')")[0]["n"]
    if "gmail" in modules:
        stats["unread"] = execute("SELECT COUNT(*) as n FROM emails WHERE is_read = 0")[0]["n"]
    if "calendar" in modules:
        stats["today_events"] = execute("SELECT COUNT(*) as n FROM calendar_events WHERE date(start_time) = date('now') AND status != 'cancelled'")[0]["n"]

    ctx["stats"] = stats
    ctx["today_formatted"] = today.strftime("%A, %B %d, %Y")

    # Urgent count for nudges
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

    # Calendar
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

        # Mark only the first non-past event as "next"
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

    # Email
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

    # Projects
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

    # Contacts
    contacts_raw = rows_to_dicts(execute(
        "SELECT id, name, company, role, email, updated_at FROM contacts WHERE status = 'active' ORDER BY updated_at DESC LIMIT 8"
    ))
    # Check for entity pages
    for c in contacts_raw:
        pages = execute("SELECT filename FROM generated_views WHERE entity_type = 'contact' AND entity_id = ?", (c["id"],))
        c["entity_page"] = pages[0]["filename"] if pages else None
    ctx["recent_contacts"] = contacts_raw

    # Follow-ups
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

    # Activity
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

    # Google connected?
    from software_of_you.db import DATA_DIR
    ctx["google_connected"] = (DATA_DIR / "google_token.json").exists()

    # Render
    html = template.render(**ctx)
    output_path = VIEWS_DIR / "dashboard.html"
    output_path.write_text(html)

    # Register
    execute_many([(
        """INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
           VALUES ('dashboard', NULL, NULL, 'Dashboard', 'dashboard.html')
           ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now')""",
        (),
    )])

    if open_after:
        _open_file(output_path)

    return {
        "result": {"path": str(output_path), "view_type": "dashboard"},
        "_context": {"presentation": "Dashboard generated and opened."},
    }


def _render_entity_page(contact_id: int, narrative_sections_json: str, open_after: bool) -> dict:
    if not contact_id:
        return {"error": "contact_id is required for entity_page."}

    rows = execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    if not rows:
        return {"error": f"No contact with id {contact_id}."}

    contact = rows_to_dicts(rows)[0]
    modules = get_installed_modules()

    # Build slug
    slug = contact["name"].lower().replace(" ", "-")
    for c in "'.()":
        slug = slug.replace(c, "")

    # Nav context
    breadcrumbs = [
        {"href": "dashboard.html", "label": "Dashboard"},
        {"href": "contacts.html", "label": "Contacts"},
        {"href": "#", "label": contact["name"]},
    ]
    other_pages = rows_to_dicts(execute(
        "SELECT entity_name, filename FROM generated_views WHERE entity_type = 'contact' AND entity_id != ? ORDER BY updated_at DESC LIMIT 5",
        (contact_id,),
    ))
    sub_nav = [{"href": p["filename"], "label": p["entity_name"]} for p in other_pages]

    ctx = _get_nav_context("contacts", "people", breadcrumbs, sub_nav)
    ctx["contact"] = contact

    # Tags
    ctx["tags"] = rows_to_dicts(execute(
        "SELECT t.name, t.color FROM tags t JOIN entity_tags et ON et.tag_id = t.id WHERE et.entity_type = 'contact' AND et.entity_id = ?",
        (contact_id,),
    ))

    # Notes
    ctx["notes"] = rows_to_dicts(execute(
        "SELECT content, created_at FROM notes WHERE entity_type = 'contact' AND entity_id = ? ORDER BY created_at DESC LIMIT 5",
        (contact_id,),
    ))

    # Emails
    if "gmail" in modules:
        emails_raw = rows_to_dicts(execute(
            "SELECT * FROM emails WHERE contact_id = ? ORDER BY received_at ASC", (contact_id,),
        ))
        for e in emails_raw:
            e["received_at_formatted"] = _relative_time(e["received_at"])
        ctx["emails"] = emails_raw

    # Events
    if "calendar" in modules:
        events_raw = rows_to_dicts(execute(
            "SELECT * FROM calendar_events WHERE contact_ids LIKE ? AND status != 'cancelled' AND start_time > datetime('now') ORDER BY start_time ASC LIMIT 5",
            (f"%{contact_id}%",),
        ))
        for e in events_raw:
            e["start_formatted"] = _format_time(e["start_time"]) + " · " + _relative_time(e["start_time"])
        ctx["upcoming_events"] = events_raw

    # Projects
    if "project-tracker" in modules:
        projects = rows_to_dicts(execute(
            "SELECT * FROM projects WHERE client_id = ?", (contact_id,),
        ))
        for p in projects:
            p["tasks"] = rows_to_dicts(execute(
                "SELECT title, status FROM tasks WHERE project_id = ? ORDER BY sort_order", (p["id"],),
            ))
        ctx["projects"] = projects

    # Follow-ups
    if "crm" in modules:
        fus = rows_to_dicts(execute(
            "SELECT * FROM follow_ups WHERE contact_id = ? AND status = 'pending' ORDER BY due_date ASC",
            (contact_id,),
        ))
        today_str = date.today().isoformat()
        for fu in fus:
            fu["overdue"] = fu["due_date"] < today_str
        ctx["follow_ups"] = fus

    # Transcripts and call intelligence
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

        # Aggregate call intelligence
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

        # Relationship score
        rs = rows_to_dicts(execute(
            "SELECT * FROM relationship_scores WHERE contact_id = ? ORDER BY score_date DESC LIMIT 1",
            (contact_id,),
        ))
        ctx["relationship_score"] = rs[0] if rs else None

    # Standalone notes
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

    # Company team
    if contact.get("company"):
        team = rows_to_dicts(execute(
            "SELECT name, role FROM contacts WHERE company = ? AND id != ? AND status = 'active'",
            (contact["company"], contact_id),
        ))
        ctx["company_team"] = team

    # Narrative sections
    ctx["narrative_sections"] = {}
    ctx["next_action"] = None
    if narrative_sections_json:
        try:
            ns = json.loads(narrative_sections_json) if isinstance(narrative_sections_json, str) else narrative_sections_json
            ctx["narrative_sections"] = ns
            ctx["next_action"] = ns.get("next_action")
        except (json.JSONDecodeError, TypeError):
            pass

    # Render
    env = _get_env()
    template = env.get_template("pages/entity_page.html")
    html = template.render(**ctx)
    output_path = VIEWS_DIR / f"contact-{slug}.html"
    output_path.write_text(html)

    # Register
    execute_many([(
        """INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
           VALUES ('entity_page', 'contact', ?, ?, ?)
           ON CONFLICT(filename) DO UPDATE SET entity_name = excluded.entity_name, updated_at = datetime('now')""",
        (contact_id, contact["name"], f"contact-{slug}.html"),
    )])

    if open_after:
        _open_file(output_path)

    return {
        "result": {"path": str(output_path), "view_type": "entity_page", "contact": contact["name"]},
        "_context": {"presentation": f"Entity page for {contact['name']} generated and opened."},
    }


def _render_module_view(sections_data_json: str, open_after: bool) -> dict:
    if not sections_data_json:
        return {"error": "sections_data JSON is required for module_view."}

    try:
        data = json.loads(sections_data_json) if isinstance(sections_data_json, str) else sections_data_json
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid sections_data JSON."}

    page_title = data.get("page_title", "View")
    filename = data.get("filename", page_title.lower().replace(" ", "-") + ".html")
    active_page = data.get("active_page", "dashboard")
    active_group = data.get("active_group", "")

    breadcrumbs = data.get("breadcrumbs", [
        {"href": "dashboard.html", "label": "Dashboard"},
        {"href": "#", "label": page_title},
    ])

    ctx = _get_nav_context(active_page, active_group, breadcrumbs)
    ctx["page_title"] = page_title
    ctx["page_subtitle"] = data.get("page_subtitle", "")
    ctx["header_stats"] = data.get("header_stats", [])
    ctx["sections"] = data.get("sections", [])

    env = _get_env()
    template = env.get_template("pages/module_view.html")
    html = template.render(**ctx)
    output_path = VIEWS_DIR / filename
    output_path.write_text(html)

    # Register
    execute_many([(
        """INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
           VALUES ('module_view', 'module', NULL, ?, ?)
           ON CONFLICT(filename) DO UPDATE SET entity_name = excluded.entity_name, updated_at = datetime('now')""",
        (page_title, filename),
    )])

    if open_after:
        _open_file(output_path)

    return {
        "result": {"path": str(output_path), "view_type": "module_view", "page": page_title},
        "_context": {"presentation": f"{page_title} view generated and opened."},
    }
