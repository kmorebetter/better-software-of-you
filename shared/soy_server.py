#!/usr/bin/env python3
"""SoY Hub — unified local server for Software of You.

Serves the hub home page, all generated HTML views, and API endpoints.

Usage:
    python3 soy_server.py          # Start on port 8787
    python3 soy_server.py 9090     # Start on custom port
"""

import json
import os
import re
import signal
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")
OUTPUT_DIR = os.path.join(PLUGIN_ROOT, "output")
DEFAULT_PORT = 8787

# ── Sidebar CSS ──────────────────────────────────────────────
SIDEBAR_CSS = """
/* ── SIDEBAR ── */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  width: 15rem;
  background: white;
  border-right: 1px solid #e4e4e7;
  display: flex;
  flex-direction: column;
  z-index: 40;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
}
@media (min-width: 1024px) {
  .sidebar { transform: translateX(0); }
}
.sidebar.open { transform: translateX(0); }

.sidebar-header {
  padding: 1rem 1rem;
  border-bottom: 1px solid #f4f4f5;
  flex-shrink: 0;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #18181b;
  text-decoration: none;
}
.sidebar-logo:hover { color: #3b82f6; }

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0.5rem;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  color: #71717a;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-item:hover {
  background: #f4f4f5;
  color: #18181b;
}
.sidebar-item.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.sidebar-item-disabled {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

.sidebar-badge {
  margin-left: auto;
  font-size: 0.6875rem;
  background: #e4e4e7;
  color: #52525b;
  padding: 0.0625rem 0.375rem;
  border-radius: 9999px;
  font-weight: 500;
  flex-shrink: 0;
}
.sidebar-item.active .sidebar-badge {
  background: #3b82f6;
  color: white;
}
.sidebar-badge-alert {
  background: #fecaca;
  color: #dc2626;
}
.sidebar-item.active .sidebar-badge-alert {
  background: #dc2626;
  color: white;
}

.sidebar-section {
  margin-top: 0.5rem;
}
.sidebar-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.375rem 0.75rem;
  font-size: 0.6875rem;
  font-weight: 600;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  background: none;
  border: none;
  font-family: inherit;
  transition: color 0.15s;
}
.sidebar-section-label:hover {
  color: #71717a;
}
.sidebar-chevron {
  transition: transform 0.15s;
  flex-shrink: 0;
}
.sidebar-section.open > .sidebar-section-label .sidebar-chevron {
  transform: rotate(90deg);
}
.sidebar-section-content {
  display: none;
  padding-top: 0.125rem;
}
.sidebar-section.open > .sidebar-section-content {
  display: block;
}

.sidebar-entity {
  display: block;
  padding: 0.25rem 0.75rem 0.25rem 1.75rem;
  font-size: 0.8125rem;
  color: #71717a;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-entity:hover {
  background: #f4f4f5;
  color: #18181b;
  border-radius: 0.375rem;
}
.sidebar-entity.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
  border-radius: 0.375rem;
}
.sidebar-entity-disabled {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

.sidebar-divider {
  height: 1px;
  background: #f4f4f5;
  margin: 0.375rem 0.75rem;
}

.sidebar-subitem {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.2rem 0.75rem 0.2rem 2.25rem;
  font-size: 0.6875rem;
  color: #a1a1aa;
  text-decoration: none;
  border-radius: 0.375rem;
  transition: all 0.15s;
}
.sidebar-subitem svg,
.sidebar-subitem i {
  width: 0.75rem !important;
  height: 0.75rem !important;
  flex-shrink: 0;
}
.sidebar-subitem:hover { background: #f4f4f5; color: #3f3f46; }
.sidebar-subitem.active { background: #eff6ff; color: #2563eb; }

.sidebar-entity-nolink {
  cursor: default;
  opacity: 0.8;
}

.sidebar-show-all {
  display: block;
  width: 100%;
  padding: 0.25rem 0.75rem 0.25rem 1.75rem;
  font-size: 0.75rem;
  color: #3b82f6;
  text-align: left;
  cursor: pointer;
  background: none;
  border: none;
  font-family: inherit;
  transition: color 0.15s;
}
.sidebar-show-all:hover { color: #1d4ed8; }

.sidebar-entity-overflow {
  display: none;
}
.sidebar-section.show-all .sidebar-entity-overflow {
  display: block;
}
.sidebar-section.show-all .sidebar-show-all {
  display: none;
}

.sidebar-tip-zone {
  padding: 0.75rem;
  border-top: 1px solid #f4f4f5;
  flex-shrink: 0;
}
.sidebar-tip {
  background: #fafafa;
  border-radius: 0.5rem;
  padding: 0.75rem;
}
.sidebar-tip-label {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #a1a1aa;
  font-weight: 600;
  margin-bottom: 0.25rem;
}
.sidebar-tip-text {
  font-size: 0.75rem;
  color: #71717a;
  line-height: 1.4;
}

.sidebar-mobile-toggle {
  position: fixed;
  top: 1rem;
  left: 1rem;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 1px solid #e4e4e7;
  border-radius: 0.5rem;
  padding: 0.5rem;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  cursor: pointer;
  color: #52525b;
}
@media (min-width: 1024px) {
  .sidebar-mobile-toggle { display: none; }
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 30;
  display: none;
}
.sidebar-backdrop.visible {
  display: block;
}
@media (min-width: 1024px) {
  .sidebar-backdrop { display: none !important; }
}

/* === Delight Layer CSS === */
@keyframes delightFadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}
.delight-card {
    opacity: 0;
    animation: delightFadeUp 0.4s ease-out forwards;
}
.delight-card:nth-child(1) { animation-delay: 0ms; }
.delight-card:nth-child(2) { animation-delay: 50ms; }
.delight-card:nth-child(3) { animation-delay: 100ms; }
.delight-card:nth-child(4) { animation-delay: 150ms; }
.delight-card:nth-child(5) { animation-delay: 200ms; }
.delight-card:nth-child(6) { animation-delay: 250ms; }

.delight-hover {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.delight-hover:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

@keyframes delightSoftPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}
.sidebar-active-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #3b82f6;
    display: inline-block;
    flex-shrink: 0;
    animation: delightSoftPulse 2.5s ease-in-out infinite;
}

.sidebar-logo-icon {
    transition: transform 0.5s ease;
}
.sidebar-logo-icon:hover {
    transform: rotate(360deg);
}

@media (prefers-reduced-motion: reduce) {
    .delight-card {
        animation: none !important;
        opacity: 1 !important;
    }
    .delight-hover:hover {
        transform: none !important;
    }
    .sidebar-active-dot {
        animation: none !important;
    }
    .sidebar-logo-icon:hover {
        transform: none !important;
    }
}
"""

# ── Sidebar JS ───────────────────────────────────────────────
SIDEBAR_JS = """
function toggleSection(id) {
  var section = document.getElementById(id);
  if (section) section.classList.toggle('open');
}
function showAllEntities(sectionId) {
  var section = document.getElementById(sectionId);
  if (section) section.classList.add('show-all');
}
function toggleSidebar() {
  var sidebar = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebar-backdrop');
  var isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    backdrop.classList.remove('visible');
  } else {
    sidebar.classList.add('open');
    backdrop.classList.add('visible');
  }
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('visible');
  }
});
"""


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_dict(row):
    return dict(row) if row else None


def _time_ago(iso_str):
    """Convert ISO datetime string to human-readable '2 days ago' format."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days
        if days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                return "just now"
            return f"{hours}h ago"
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return iso_str


def _esc(s):
    """HTML-escape a string."""
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_sidebar(active_page="hub"):
    """Build the sidebar HTML from current database state.

    active_page: 'hub', 'dashboard', or a filename like 'contact-daniel-byrne.html'
    """
    conn = _get_db()

    # Installed modules
    modules = [r["name"] for r in conn.execute(
        "SELECT name FROM modules WHERE enabled = 1"
    ).fetchall()]

    # Badge counts
    badge_counts = {}
    for row in conn.execute("""
        SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
        UNION ALL SELECT 'emails', COUNT(*) FROM emails
        UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
        UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
        UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
        UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries
        UNION ALL SELECT 'notes', COUNT(*) FROM standalone_notes
    """).fetchall():
        badge_counts[row["section"]] = row["count"]

    # Generated module views (filename → entity_name)
    gen_module_views = {}
    for r in conn.execute(
        "SELECT entity_name, filename FROM generated_views WHERE view_type = 'module_view'"
    ).fetchall():
        gen_module_views[r["filename"]] = r["entity_name"]

    # All generated view filenames for link-or-disable check
    gen_filenames = set()
    for r in conn.execute("SELECT filename FROM generated_views").fetchall():
        gen_filenames.add(r["filename"])

    # Contact entity pages
    contact_pages = conn.execute("""
        SELECT entity_id, entity_name, filename FROM generated_views
        WHERE view_type = 'entity_page' AND entity_type = 'contact'
        ORDER BY entity_name ASC
    """).fetchall()

    # Project entity pages
    project_pages = conn.execute("""
        SELECT entity_id, entity_name, filename FROM generated_views
        WHERE view_type = 'entity_page' AND entity_type = 'project'
        ORDER BY entity_name ASC
    """).fetchall()

    # All project-linked sub-views (PM reports, prep docs, etc.)
    project_sub_views = conn.execute("""
        SELECT entity_id, entity_name, filename, view_type FROM generated_views
        WHERE entity_type = 'project' AND view_type NOT IN ('entity_page')
        ORDER BY entity_name ASC
    """).fetchall()

    # Also fetch project names for sub-views that don't have an entity page yet
    all_projects = conn.execute("""
        SELECT id, name FROM projects ORDER BY name ASC
    """).fetchall()

    # Urgent nudge count
    urgent_count = 0
    try:
        row = conn.execute("""
            SELECT
              (SELECT COUNT(*) FROM follow_ups WHERE status = 'pending' AND due_date < date('now'))
              + (SELECT COUNT(*) FROM commitments WHERE status IN ('open','overdue') AND deadline_date < date('now'))
              + (SELECT COUNT(*) FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.status NOT IN ('done') AND t.due_date < date('now'))
              as urgent_count
        """).fetchone()
        if row:
            urgent_count = row["urgent_count"] or 0
    except Exception:
        pass

    conn.close()

    # Helper: render a sidebar item (link or disabled span)
    def _sidebar_item(filename, icon, label, badge=None, badge_alert=False):
        active_cls = " active" if active_page == filename else ""
        badge_html = ""
        if badge and badge > 0:
            alert_cls = " sidebar-badge-alert" if badge_alert else ""
            badge_html = f'<span class="sidebar-badge{alert_cls}">{badge}</span>'
        if filename in gen_filenames:
            return f'''<a href="/pages/{_esc(filename)}" class="sidebar-item{active_cls}">
              <i data-lucide="{icon}" class="w-4 h-4"></i>
              {_esc(label)}
              {badge_html}
            </a>'''
        else:
            return f'''<span class="sidebar-item sidebar-item-disabled" title="Run the command to generate this view">
              <i data-lucide="{icon}" class="w-4 h-4"></i>
              {_esc(label)}
            </span>'''

    # Helper: render entity page links
    def _entity_links(pages, cap=10):
        html = ""
        for i, p in enumerate(pages):
            overflow = " sidebar-entity-overflow" if i >= cap else ""
            active_cls = " active" if active_page == p["filename"] else ""
            html += f'<a href="/pages/{_esc(p["filename"])}" class="sidebar-entity{active_cls}{overflow}">{_esc(p["entity_name"])}</a>\n'
        if len(pages) > cap:
            html += f'<button class="sidebar-show-all" onclick="showAllEntities(\'section-people\')">Show all ({len(pages)})</button>'
        return html

    # Determine which section should be open
    open_section = None
    if active_page == "hub":
        open_section = None  # No section auto-expanded on hub
    elif active_page == "dashboard.html":
        open_section = None
    elif any(active_page == p["filename"] for p in contact_pages):
        open_section = "section-people"
    elif active_page in ("contacts.html", "network-map.html"):
        open_section = "section-people"
    elif any(active_page == p["filename"] for p in project_pages) or \
         any(active_page == sv["filename"] for sv in project_sub_views):
        open_section = "section-projects"
    elif active_page in ("email-hub.html", "week-view.html"):
        open_section = "section-comms"
    elif active_page in ("conversations.html", "decision-journal.html", "journal.html", "notes.html"):
        open_section = "section-intelligence"
    elif active_page in ("weekly-review.html", "nudges.html", "timeline.html", "search.html"):
        open_section = "section-tools"

    def _section_open(section_id):
        return " open" if open_section == section_id else ""

    # Module names are stored lowercase/hyphenated in the DB
    mod_set = set(m.lower() for m in modules)
    has_crm = "crm" in mod_set
    has_projects = "project-tracker" in mod_set
    has_gmail = "gmail" in mod_set
    has_calendar = "calendar" in mod_set
    has_comms = has_gmail or has_calendar
    has_conversations = "conversation-intelligence" in mod_set
    has_decisions = "decision-log" in mod_set
    has_journal = "journal" in mod_set
    has_notes = "notes" in mod_set
    has_intel = has_conversations or has_decisions or has_journal or has_notes

    # Build sections
    people_section = ""
    if has_crm:
        contact_links = ""
        if contact_pages:
            contact_links = '<div class="sidebar-divider"></div>\n' + _entity_links(contact_pages)
        people_section = f'''
    <div class="sidebar-section{_section_open('section-people')}" id="section-people">
      <button class="sidebar-section-label" onclick="toggleSection('section-people')">
        <span>People</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        {_sidebar_item("contacts.html", "users", "Contacts", badge_counts.get("contacts"))}
        {_sidebar_item("network-map.html", "share-2", "Network Map")}
        {contact_links}
      </div>
    </div>'''

    projects_section = ""
    if has_projects:
        # Build a map of project_id -> {name, entity_page, sub_views}
        project_map = {}
        # Seed from entity pages
        for p in project_pages:
            pid = p["entity_id"]
            project_map[pid] = {
                "name": p["entity_name"],
                "entity_filename": p["filename"],
                "sub_views": [],
            }
        # Add sub-views (PM reports, prep docs, etc.)
        for sv in project_sub_views:
            pid = sv["entity_id"]
            if pid not in project_map:
                # Project has sub-views but no entity page — find name from projects table
                proj_name = sv["entity_name"]
                for proj in all_projects:
                    if proj["id"] == pid:
                        proj_name = proj["name"]
                        break
                project_map[pid] = {
                    "name": proj_name,
                    "entity_filename": None,
                    "sub_views": [],
                }
            project_map[pid]["sub_views"].append(sv)

        # Also add projects that have no views at all but exist in the DB
        # (skip — only show projects that have at least one generated view)

        # Render each project group
        view_type_labels = {
            "pm_report": "PM Report",
            "prep_page": "Prep Doc",
            "project_brief": "Brief",
            "project_analysis": "Analysis",
        }
        view_type_icons = {
            "pm_report": "brain",
            "prep_page": "clipboard-check",
            "project_brief": "file-text",
            "project_analysis": "scan-search",
        }

        project_links = ""
        for pid in sorted(project_map, key=lambda k: project_map[k]["name"]):
            pm = project_map[pid]
            # Main project link (entity page) or just a label
            if pm["entity_filename"]:
                active_cls = " active" if active_page == pm["entity_filename"] else ""
                project_links += f'<a href="/pages/{_esc(pm["entity_filename"])}" class="sidebar-entity{active_cls}">{_esc(pm["name"])}</a>\n'
            else:
                project_links += f'<span class="sidebar-entity sidebar-entity-nolink">{_esc(pm["name"])}</span>\n'
            # Sub-view links indented beneath
            for sv in pm["sub_views"]:
                active_cls = " active" if active_page == sv["filename"] else ""
                label = view_type_labels.get(sv["view_type"], sv["view_type"])
                icon = view_type_icons.get(sv["view_type"], "file")
                project_links += (
                    f'<a href="/pages/{_esc(sv["filename"])}" class="sidebar-subitem{active_cls}">'
                    f'<i data-lucide="{icon}" class="w-3 h-3"></i> {_esc(label)}</a>\n'
                )

        projects_section = f'''
    <div class="sidebar-section{_section_open('section-projects')}" id="section-projects">
      <button class="sidebar-section-label" onclick="toggleSection('section-projects')">
        <span>Projects</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        {project_links}
      </div>
    </div>'''

    comms_section = ""
    if has_comms:
        email_item = _sidebar_item("email-hub.html", "mail", "Email", badge_counts.get("emails")) if has_gmail else ""
        cal_item = _sidebar_item("week-view.html", "calendar", "Calendar", badge_counts.get("calendar")) if has_calendar else ""
        comms_section = f'''
    <div class="sidebar-section{_section_open('section-comms')}" id="section-comms">
      <button class="sidebar-section-label" onclick="toggleSection('section-comms')">
        <span>Comms</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        {email_item}
        {cal_item}
      </div>
    </div>'''

    intel_section = ""
    if has_intel:
        items = ""
        if has_conversations:
            items += _sidebar_item("conversations.html", "message-square", "Conversations")
        if has_decisions:
            items += _sidebar_item("decision-journal.html", "git-branch", "Decisions")
        if has_journal:
            items += _sidebar_item("journal.html", "book-open", "Journal")
        if has_notes:
            items += _sidebar_item("notes.html", "sticky-note", "Notes")
        intel_section = f'''
    <div class="sidebar-section{_section_open('section-intelligence')}" id="section-intelligence">
      <button class="sidebar-section-label" onclick="toggleSection('section-intelligence')">
        <span>Intelligence</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        {items}
      </div>
    </div>'''

    # Tools section (always present)
    nudge_badge = urgent_count if urgent_count > 0 else None
    tools_section = f'''
    <div class="sidebar-section{_section_open('section-tools')}" id="section-tools">
      <button class="sidebar-section-label" onclick="toggleSection('section-tools')">
        <span>Tools</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5 sidebar-chevron"></i>
      </button>
      <div class="sidebar-section-content">
        {_sidebar_item("weekly-review.html", "clipboard-list", "Weekly Review")}
        {_sidebar_item("nudges.html", "bell", "Nudges", nudge_badge, badge_alert=True)}
        {_sidebar_item("timeline.html", "clock", "Timeline")}
        {_sidebar_item("search.html", "search", "Search")}
      </div>
    </div>'''

    # Hub active state
    hub_active = " active" if active_page == "hub" else ""
    dash_active = " active" if active_page == "dashboard.html" else ""

    # Dashboard link
    dash_link = ""
    if "dashboard.html" in gen_filenames:
        dash_link = f'''<a href="/pages/dashboard.html" class="sidebar-item{dash_active}">
      <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
      Dashboard
    </a>'''
    else:
        dash_link = '''<span class="sidebar-item sidebar-item-disabled" title="Run /dashboard to generate">
      <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
      Dashboard
    </span>'''

    return f'''<aside id="sidebar" class="sidebar">
  <div class="sidebar-header">
    <a href="/" class="sidebar-logo">
      <i data-lucide="hexagon" class="w-4 h-4 sidebar-logo-icon"></i>
      <span>Software of You</span>
    </a>
  </div>
  <nav class="sidebar-nav">
    <a href="/" class="sidebar-item{hub_active}">
      <i data-lucide="home" class="w-4 h-4"></i>
      Hub
    </a>
    {dash_link}
    {people_section}
    {projects_section}
    {comms_section}
    {intel_section}
    {tools_section}
  </nav>
  <div style="padding:0.25rem 0.5rem;">
    <button class="dark-toggle" onclick="toggleDarkMode()" title="Toggle dark mode">
      <svg id="dark-icon-sun" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      <svg id="dark-icon-moon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      <span id="dark-toggle-label">Dark mode</span>
    </button>
  </div>
  <div class="sidebar-tip-zone">
    <div class="sidebar-tip">
      <p class="sidebar-tip-label">Tip</p>
      <p class="sidebar-tip-text">Use /help-soy to see all available commands.</p>
    </div>
  </div>
</aside>

<button id="sidebar-toggle" class="sidebar-mobile-toggle" onclick="toggleSidebar()">
  <i data-lucide="menu" class="w-5 h-5"></i>
</button>
<div id="sidebar-backdrop" class="sidebar-backdrop" onclick="toggleSidebar()"></div>'''


SUBNAV_CSS = """
.section-subnav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(250,250,250,0.95);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid #e4e4e7;
  padding: 0.5rem 0;
  margin-bottom: 1.5rem;
}
.section-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  color: #71717a;
  text-decoration: none;
  white-space: nowrap;
  transition: all 0.15s;
}
.section-pill:hover {
  color: #7c3aed;
  background: rgba(139, 92, 246, 0.08);
}
.section-pill.active {
  color: #7c3aed;
  background: rgba(139, 92, 246, 0.1);
}
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }
"""

SUBNAV_JS = """
// Scrollspy for section pills
(function() {
  var pills = document.querySelectorAll('.section-pill');
  if (!pills.length) return;
  var pillSections = [];
  pills.forEach(function(pill) {
    var id = pill.getAttribute('href');
    if (!id || id.charAt(0) !== '#') return;
    var el = document.getElementById(id.substring(1));
    if (el) pillSections.push({ el: el, pill: pill });
  });
  function updatePills() {
    var scrollY = window.scrollY + 140;
    var current = pillSections[0];
    for (var i = 0; i < pillSections.length; i++) {
      if (pillSections[i].el.offsetTop <= scrollY) current = pillSections[i];
    }
    pills.forEach(function(p) { p.classList.remove('active'); });
    if (current) current.pill.classList.add('active');
  }
  window.addEventListener('scroll', updatePills);
  updatePills();
})();
"""

# ── Dark Mode CSS ─────────────────────────────────────────────
DARKMODE_CSS = """
/* ── DARK MODE OVERRIDES ── */
/* Surfaces */
html.dark body { background-color: #18181b !important; color: #fafafa !important; }
html.dark .bg-zinc-50 { background-color: #18181b !important; }
html.dark .bg-white { background-color: #27272a !important; }
html.dark .bg-zinc-100 { background-color: #3f3f46 !important; }
html.dark .bg-zinc-200 { background-color: #52525b !important; }
html.dark .bg-zinc-900:not(pre):not(code) { background-color: #fafafa !important; }
html.dark pre.bg-zinc-900, html.dark pre[class*="bg-zinc-9"] { background-color: #0f0f14 !important; color: #e4e4e7 !important; }

/* Text */
html.dark .text-zinc-900 { color: #fafafa !important; }
html.dark .text-zinc-800 { color: #e4e4e7 !important; }
html.dark .text-zinc-700 { color: #d4d4d8 !important; }
html.dark .text-zinc-600 { color: #a1a1aa !important; }
html.dark .text-zinc-500 { color: #a1a1aa !important; }
html.dark .text-zinc-400 { color: #71717a !important; }
html.dark .text-white { color: #18181b !important; }

/* Borders */
html.dark .border-zinc-200 { border-color: #3f3f46 !important; }
html.dark .border-zinc-100 { border-color: #3f3f46 !important; }
html.dark .border-zinc-300 { border-color: #52525b !important; }
html.dark .divide-zinc-200 > :not([hidden]) ~ :not([hidden]) { border-color: #3f3f46 !important; }
html.dark .divide-zinc-100 > :not([hidden]) ~ :not([hidden]) { border-color: #3f3f46 !important; }

/* Shadows */
html.dark [class*="shadow"] { --tw-shadow-color: rgba(0,0,0,0.3) !important; }

/* Accent tint backgrounds */
html.dark .bg-blue-50 { background-color: rgba(59,130,246,0.12) !important; }
html.dark .bg-green-50 { background-color: rgba(34,197,94,0.12) !important; }
html.dark .bg-amber-50 { background-color: rgba(245,158,11,0.12) !important; }
html.dark .bg-red-50 { background-color: rgba(239,68,68,0.12) !important; }
html.dark .bg-purple-50 { background-color: rgba(168,85,247,0.12) !important; }
html.dark .bg-violet-50 { background-color: rgba(139,92,246,0.12) !important; }
html.dark .bg-indigo-50 { background-color: rgba(99,102,241,0.12) !important; }
html.dark .bg-orange-50 { background-color: rgba(249,115,22,0.12) !important; }
html.dark .bg-yellow-50 { background-color: rgba(234,179,8,0.12) !important; }
html.dark .bg-emerald-50 { background-color: rgba(16,185,129,0.12) !important; }
html.dark .bg-teal-50 { background-color: rgba(20,184,166,0.12) !important; }
html.dark .bg-cyan-50 { background-color: rgba(6,182,212,0.12) !important; }
html.dark .bg-sky-50 { background-color: rgba(14,165,233,0.12) !important; }
html.dark .bg-rose-50 { background-color: rgba(244,63,94,0.12) !important; }
html.dark .bg-pink-50 { background-color: rgba(236,72,153,0.12) !important; }
html.dark .bg-fuchsia-50 { background-color: rgba(192,38,211,0.12) !important; }

/* Accent -100 backgrounds */
html.dark .bg-blue-100 { background-color: rgba(59,130,246,0.2) !important; }
html.dark .bg-green-100 { background-color: rgba(34,197,94,0.2) !important; }
html.dark .bg-emerald-100 { background-color: rgba(16,185,129,0.2) !important; }
html.dark .bg-violet-100 { background-color: rgba(139,92,246,0.2) !important; }
html.dark .bg-purple-100 { background-color: rgba(168,85,247,0.2) !important; }
html.dark .bg-amber-100 { background-color: rgba(245,158,11,0.2) !important; }
html.dark .bg-red-100 { background-color: rgba(239,68,68,0.2) !important; }
html.dark .bg-indigo-100 { background-color: rgba(99,102,241,0.2) !important; }
html.dark .bg-orange-100 { background-color: rgba(249,115,22,0.2) !important; }
html.dark .bg-yellow-100 { background-color: rgba(234,179,8,0.2) !important; }
html.dark .bg-teal-100 { background-color: rgba(20,184,166,0.2) !important; }
html.dark .bg-cyan-100 { background-color: rgba(6,182,212,0.2) !important; }
html.dark .bg-sky-100 { background-color: rgba(14,165,233,0.2) !important; }
html.dark .bg-rose-100 { background-color: rgba(244,63,94,0.2) !important; }
html.dark .bg-pink-100 { background-color: rgba(236,72,153,0.2) !important; }
html.dark .bg-fuchsia-100 { background-color: rgba(192,38,211,0.2) !important; }

/* Accent -200 backgrounds */
html.dark .bg-blue-200 { background-color: rgba(59,130,246,0.25) !important; }
html.dark .bg-green-200 { background-color: rgba(34,197,94,0.25) !important; }
html.dark .bg-violet-200 { background-color: rgba(139,92,246,0.25) !important; }

/* Gradient overrides — must override background-image directly since
   Tailwind CDN bakes the gradient inline and CSS var !important won't propagate */
html.dark .bg-gradient-to-b.from-blue-50.to-white { background-image: linear-gradient(to bottom, rgba(59,130,246,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-green-50.to-white { background-image: linear-gradient(to bottom, rgba(34,197,94,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-amber-50.to-white { background-image: linear-gradient(to bottom, rgba(245,158,11,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-violet-50.to-white { background-image: linear-gradient(to bottom, rgba(139,92,246,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-purple-50.to-white { background-image: linear-gradient(to bottom, rgba(168,85,247,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-emerald-50.to-white { background-image: linear-gradient(to bottom, rgba(16,185,129,0.12), #27272a) !important; }
html.dark .bg-gradient-to-b.from-red-50.to-white { background-image: linear-gradient(to bottom, rgba(239,68,68,0.12), #27272a) !important; }
html.dark .bg-gradient-to-r.from-blue-50.to-white { background-image: linear-gradient(to right, rgba(59,130,246,0.12), #27272a) !important; }
html.dark .bg-gradient-to-r.from-green-50.to-white { background-image: linear-gradient(to right, rgba(34,197,94,0.12), #27272a) !important; }
html.dark .bg-gradient-to-r.from-violet-50.to-white { background-image: linear-gradient(to right, rgba(139,92,246,0.12), #27272a) !important; }
/* Catch-all: any gradient ending in to-white on a bg-white-overridden surface */
html.dark .bg-gradient-to-b.to-white { --tw-gradient-to: #27272a !important; }
html.dark .bg-gradient-to-r.to-white { --tw-gradient-to: #27272a !important; }
html.dark .bg-gradient-to-b.to-zinc-50 { --tw-gradient-to: #18181b !important; }
html.dark .bg-gradient-to-br.from-blue-50.to-white { background-image: linear-gradient(to bottom right, rgba(59,130,246,0.12), #27272a) !important; }
html.dark .bg-gradient-to-br.from-violet-50.to-white { background-image: linear-gradient(to bottom right, rgba(139,92,246,0.12), #27272a) !important; }

/* Accent border colors */
html.dark .border-blue-100 { border-color: rgba(59,130,246,0.25) !important; }
html.dark .border-blue-200 { border-color: rgba(59,130,246,0.3) !important; }
html.dark .border-green-100 { border-color: rgba(34,197,94,0.25) !important; }
html.dark .border-green-200 { border-color: rgba(34,197,94,0.3) !important; }
html.dark .border-emerald-100 { border-color: rgba(16,185,129,0.25) !important; }
html.dark .border-emerald-200 { border-color: rgba(16,185,129,0.3) !important; }
html.dark .border-violet-100 { border-color: rgba(139,92,246,0.25) !important; }
html.dark .border-violet-200 { border-color: rgba(139,92,246,0.3) !important; }
html.dark .border-amber-100 { border-color: rgba(245,158,11,0.25) !important; }
html.dark .border-amber-200 { border-color: rgba(245,158,11,0.3) !important; }
html.dark .border-red-100 { border-color: rgba(239,68,68,0.25) !important; }
html.dark .border-red-200 { border-color: rgba(239,68,68,0.3) !important; }

/* Accent text: lighten -700 and -800 variants for dark bg contrast */
html.dark .text-blue-700 { color: #93c5fd !important; }
html.dark .text-blue-800 { color: #93c5fd !important; }
html.dark .text-blue-600 { color: #60a5fa !important; }
html.dark .text-green-700 { color: #86efac !important; }
html.dark .text-green-600 { color: #4ade80 !important; }
html.dark .text-emerald-700 { color: #6ee7b7 !important; }
html.dark .text-emerald-600 { color: #34d399 !important; }
html.dark .text-emerald-500 { color: #34d399 !important; }
html.dark .text-violet-700 { color: #c4b5fd !important; }
html.dark .text-violet-600 { color: #a78bfa !important; }
html.dark .text-purple-700 { color: #d8b4fe !important; }
html.dark .text-purple-600 { color: #c084fc !important; }
html.dark .text-amber-700 { color: #fcd34d !important; }
html.dark .text-amber-600 { color: #fbbf24 !important; }
html.dark .text-red-700 { color: #fca5a5 !important; }
html.dark .text-red-600 { color: #f87171 !important; }
html.dark .text-orange-700 { color: #fdba74 !important; }
html.dark .text-orange-600 { color: #fb923c !important; }

/* Opacity modifier backgrounds (Tailwind bg-*/50 syntax) */
html.dark [class*="bg-blue-50\\/"] { background-color: rgba(59,130,246,0.08) !important; }
html.dark [class*="bg-green-50\\/"] { background-color: rgba(34,197,94,0.08) !important; }
html.dark [class*="bg-emerald-50\\/"] { background-color: rgba(16,185,129,0.08) !important; }

/* Border-l accent colors */
html.dark .border-l-blue-200, html.dark [class*="border-blue-200"] { border-color: rgba(59,130,246,0.3) !important; }

/* Opacity-modifier accent backgrounds (Tailwind bg-color-shade/opacity) */
html.dark [class*="bg-rose-50\\/"] { background-color: rgba(244,63,94,0.08) !important; }
html.dark [class*="bg-violet-50\\/"] { background-color: rgba(139,92,246,0.08) !important; }
html.dark [class*="bg-purple-50\\/"] { background-color: rgba(168,85,247,0.08) !important; }
html.dark [class*="bg-amber-50\\/"] { background-color: rgba(245,158,11,0.08) !important; }
html.dark [class*="bg-indigo-50\\/"] { background-color: rgba(99,102,241,0.08) !important; }

/* Rose accent borders */
html.dark .border-rose-100 { border-color: rgba(244,63,94,0.25) !important; }
html.dark .border-rose-200 { border-color: rgba(244,63,94,0.3) !important; }
html.dark .border-rose-300 { border-color: rgba(244,63,94,0.4) !important; }
html.dark .border-pink-100 { border-color: rgba(236,72,153,0.25) !important; }
html.dark .border-pink-200 { border-color: rgba(236,72,153,0.3) !important; }
html.dark .border-purple-100 { border-color: rgba(168,85,247,0.25) !important; }
html.dark .border-purple-200 { border-color: rgba(168,85,247,0.3) !important; }
html.dark .border-indigo-100 { border-color: rgba(99,102,241,0.25) !important; }
html.dark .border-indigo-200 { border-color: rgba(99,102,241,0.3) !important; }

/* Rose/pink accent text */
html.dark .text-rose-500 { color: #fb7185 !important; }
html.dark .text-rose-600 { color: #fb7185 !important; }
html.dark .text-rose-700 { color: #fda4af !important; }
html.dark .text-pink-500 { color: #f472b6 !important; }
html.dark .text-pink-600 { color: #f472b6 !important; }
html.dark .text-indigo-600 { color: #818cf8 !important; }
html.dark .text-indigo-700 { color: #a5b4fc !important; }
html.dark .text-violet-500 { color: #a78bfa !important; }

/* PM Report outcome badges (hardcoded in page <style>, need html.dark override) */
html.dark .outcome-completed { background: rgba(16,185,129,0.15) !important; color: #6ee7b7 !important; }
html.dark .outcome-partial { background: rgba(245,158,11,0.15) !important; color: #fcd34d !important; }
html.dark .outcome-blocked { background: rgba(239,68,68,0.15) !important; color: #fca5a5 !important; }
html.dark .outcome-none { background: rgba(63,63,70,0.5) !important; color: #a1a1aa !important; }

/* PM Report sidebar-link (inline styles in page) */
html.dark .sidebar-link { color: #a1a1aa !important; }
html.dark .sidebar-link:hover { background: rgba(139,92,246,0.15) !important; color: #a78bfa !important; }
html.dark .sidebar-link.active { background: rgba(139,92,246,0.15) !important; color: #a78bfa !important; }

/* Delight layer dark overrides */
html.dark .delight-row:hover { background-color: rgba(63,63,70,0.5) !important; }
html.dark .delight-hover:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important; }

/* Sidebar */
html.dark .sidebar { background: #1f1f23 !important; border-right-color: #3f3f46 !important; }
html.dark .sidebar-header { border-bottom-color: #3f3f46 !important; }
html.dark .sidebar-logo { color: #e4e4e7 !important; }
html.dark .sidebar-item { color: #a1a1aa !important; }
html.dark .sidebar-item:hover { background: #3f3f46 !important; color: #fafafa !important; }
html.dark .sidebar-item.active { background: rgba(59,130,246,0.15) !important; color: #60a5fa !important; }
html.dark .sidebar-entity { color: #a1a1aa !important; }
html.dark .sidebar-entity:hover { background: #3f3f46 !important; color: #fafafa !important; }
html.dark .sidebar-entity.active { background: rgba(59,130,246,0.15) !important; color: #60a5fa !important; }
html.dark .sidebar-subitem { color: #71717a !important; }
html.dark .sidebar-subitem:hover { background: #3f3f46 !important; color: #a1a1aa !important; }
html.dark .sidebar-subitem.active { background: rgba(59,130,246,0.15) !important; color: #60a5fa !important; }
html.dark .sidebar-badge { background: #3f3f46 !important; color: #a1a1aa !important; }
html.dark .sidebar-badge-alert { background: rgba(239,68,68,0.2) !important; color: #f87171 !important; }
html.dark .sidebar-divider { background: #3f3f46 !important; }
html.dark .sidebar-section-label { color: #71717a !important; }
html.dark .sidebar-section-label:hover { color: #a1a1aa !important; }
html.dark .sidebar-tip-zone { border-top-color: #3f3f46 !important; }
html.dark .sidebar-tip { background: #27272a !important; }
html.dark .sidebar-tip-label { color: #71717a !important; }
html.dark .sidebar-tip-text { color: #a1a1aa !important; }
html.dark .sidebar-mobile-toggle { background: #27272a !important; border-color: #3f3f46 !important; color: #a1a1aa !important; }
html.dark .sidebar-backdrop { background: rgba(0,0,0,0.6) !important; }

/* Subnav */
html.dark .section-subnav { background: rgba(24,24,27,0.95) !important; border-bottom-color: #3f3f46 !important; }
html.dark .section-pill { color: #a1a1aa !important; }
html.dark .section-pill:hover { color: #a78bfa !important; background: rgba(139,92,246,0.15) !important; }
html.dark .section-pill.active { color: #a78bfa !important; background: rgba(139,92,246,0.15) !important; }

/* Hover states */
html.dark .hover\\:bg-zinc-50:hover { background-color: #3f3f46 !important; }
html.dark .hover\\:bg-zinc-100:hover { background-color: #52525b !important; }
html.dark .hover\\:bg-white:hover { background-color: #3f3f46 !important; }
html.dark .hover\\:border-zinc-300:hover { border-color: #52525b !important; }
html.dark .hover\\:border-blue-300:hover { border-color: rgba(59,130,246,0.4) !important; }
html.dark .hover\\:border-violet-300:hover { border-color: rgba(139,92,246,0.4) !important; }
html.dark .hover\\:text-zinc-700:hover { color: #d4d4d8 !important; }

/* Inputs and code blocks */
html.dark input, html.dark textarea, html.dark select { background-color: #27272a !important; border-color: #3f3f46 !important; color: #fafafa !important; }
html.dark code { background-color: #3f3f46 !important; color: #e4e4e7 !important; }
html.dark pre { background-color: #27272a !important; color: #e4e4e7 !important; }

/* Tables */
html.dark th { background-color: #27272a !important; color: #d4d4d8 !important; border-color: #3f3f46 !important; }
html.dark td { border-color: #3f3f46 !important; }
html.dark tr:hover td { background-color: rgba(63,63,70,0.5) !important; }

/* Ring / focus */
html.dark .ring-zinc-200 { --tw-ring-color: #3f3f46 !important; }
html.dark .ring-zinc-100 { --tw-ring-color: #3f3f46 !important; }

/* Dark toggle button */
.dark-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  color: #71717a;
  cursor: pointer;
  background: none;
  border: none;
  font-family: inherit;
  width: 100%;
  transition: all 0.15s;
}
.dark-toggle:hover { background: #f4f4f5; color: #18181b; }
html.dark .dark-toggle { color: #a1a1aa !important; }
html.dark .dark-toggle:hover { background: #3f3f46 !important; color: #fafafa !important; }
.dark-toggle svg { width: 1rem; height: 1rem; flex-shrink: 0; }
"""

# ── Dark Mode JS ──────────────────────────────────────────────
DARKMODE_JS = """
// Dark mode toggle
(function() {
  function updateDarkToggleIcon() {
    var sunIcon = document.getElementById('dark-icon-sun');
    var moonIcon = document.getElementById('dark-icon-moon');
    var label = document.getElementById('dark-toggle-label');
    if (!sunIcon || !moonIcon) return;
    var isDark = document.documentElement.classList.contains('dark');
    sunIcon.style.display = isDark ? 'none' : 'block';
    moonIcon.style.display = isDark ? 'block' : 'none';
    if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
  }
  window.toggleDarkMode = function() {
    var isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('soy-dark-mode', isDark ? 'dark' : 'light');
    updateDarkToggleIcon();
  };
  // System preference listener (only applies when user hasn't explicitly chosen)
  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
      if (!localStorage.getItem('soy-dark-mode')) {
        if (e.matches) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        updateDarkToggleIcon();
      }
    });
  } catch(e) {}
  // Update icon on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateDarkToggleIcon);
  } else {
    updateDarkToggleIcon();
  }
})();
"""

# ── Dark Mode Init (synchronous, prevents FOUC) ──────────────
DARKMODE_INIT = """<script>(function(){var s=localStorage.getItem('soy-dark-mode');if(s==='dark'||(s!=='light'&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}})()</script>"""


def _inject_sidebar_into_page(html, filename):
    """Inject the global SoY sidebar into a served page.

    - Builds a fresh sidebar from the DB with the correct active state
    - Detects existing in-page sidebars (PM reports) and converts them
      to a horizontal sticky sub-nav within the content area
    - Adds sidebar CSS/JS if not present
    - Adjusts <main> margin for sidebar offset
    """
    sidebar_html = _build_sidebar(active_page=filename)

    # ── Strip any existing hardcoded sidebar ───────────────────
    # Pages generated before server-side injection have stale sidebars
    # that are missing new pages, Hub link, etc. Always replace them.
    if 'id="sidebar"' in html:
        html = re.sub(
            r'<aside\s+id="sidebar"[^>]*>.*?</aside>',
            '', html, count=1, flags=re.DOTALL,
        )

    # ── Handle existing in-page sidebar (PM reports) ─────────
    # These are section-navigation asides (not id="sidebar"), like
    # the fixed left nav in PM reports with anchor links.
    in_page_nav = ""
    aside_match = re.search(
        r'<aside\s[^>]*class="fixed[^"]*"[^>]*>.*?</aside>',
        html, re.DOTALL,
    )
    if aside_match:
        aside_html = aside_match.group()
        # Extract anchor links: <a href="#id" ...><i ...></i> Label</a>
        nav_links = re.findall(
            r'<a\s+href="#([^"]+)"[^>]*>\s*(?:<i[^>]*></i>\s*)?([^<]+)',
            aside_html,
        )
        if nav_links:
            pills = []
            for href_id, label in nav_links:
                pills.append(
                    f'<a href="#{_esc(href_id.strip())}" '
                    f'class="section-pill">{_esc(label.strip())}</a>'
                )
            in_page_nav = (
                '<div class="section-subnav">'
                '<div class="flex items-center gap-1 overflow-x-auto no-scrollbar">'
                + "".join(pills)
                + "</div></div>"
            )
        # Remove the old aside
        html = html[: aside_match.start()] + html[aside_match.end() :]

    # ── Inject dark mode init script in <head> (prevents FOUC) ─
    if "soy-dark-mode" not in html:
        html = html.replace("<head>", "<head>\n" + DARKMODE_INIT, 1)

    # ── Inject sidebar CSS ────────────────────────────────────
    # Always strip any stale sidebar CSS and inject the current version.
    # Pages with hardcoded sidebars have old CSS missing new rules.
    if ".sidebar-subitem" not in html:
        # Old sidebar CSS exists but is incomplete — replace it
        if ".sidebar {" in html or ".sidebar{" in html:
            html = re.sub(
                r'(/\*\s*sidebar\s*\*/\s*)?\.sidebar\s*\{[^}]*\}.*?(?=\n\s*</style>|\n\s*/\*(?!.*sidebar))',
                '', html, count=1, flags=re.DOTALL | re.IGNORECASE,
            )
        css_block = f"<style>{SIDEBAR_CSS}\n{SUBNAV_CSS}\n{DARKMODE_CSS}</style>"
        html = html.replace("</head>", css_block + "\n</head>", 1)
    elif ".section-subnav" not in html and in_page_nav:
        html = html.replace("</style>", SUBNAV_CSS + "\n</style>", 1)

    # Inject dark mode CSS if not already present (sidebar CSS was already there)
    if "DARK MODE OVERRIDES" not in html:
        # Find last </style> and inject before it
        last_style = html.rfind("</style>")
        if last_style > 0:
            html = html[:last_style] + "\n" + DARKMODE_CSS + "\n" + html[last_style:]

    # ── Inject sidebar HTML after <body> ──────────────────────
    body_match = re.search(r"<body[^>]*>", html)
    if body_match:
        pos = body_match.end()
        html = html[:pos] + "\n" + sidebar_html + "\n" + html[pos:]

    # ── Adjust <main> margin ──────────────────────────────────
    # Replace any existing ml-56 (PM reports) with ml-60
    html = html.replace("lg:ml-56", "lg:ml-60")
    # Add lg:ml-60 if main doesn't have it
    if "lg:ml-60" not in html:
        # main with existing class
        html, n = re.subn(
            r'<main\s+class="([^"]*)"',
            lambda m: f'<main class="lg:ml-60 {m.group(1)}"',
            html, count=1,
        )
        if n == 0:
            html = re.sub(
                r"<main(?=[\s>])", '<main class="lg:ml-60"', html, count=1
            )

    # ── Inject in-page sub-nav at top of main content ─────────
    if in_page_nav:
        # Insert after the first <div> inside <main>
        main_div_match = re.search(
            r"(<main[^>]*>\s*<div[^>]*>)", html
        )
        if main_div_match:
            pos = main_div_match.end()
            html = html[:pos] + "\n" + in_page_nav + "\n" + html[pos:]

    # ── Inject sidebar + subnav + dark mode JS if not present ──
    if "toggleSidebar" not in html:
        js_block = f"<script>\n{SIDEBAR_JS}\n{SUBNAV_JS}\n{DARKMODE_JS}\n</script>"
        html = html.replace("</body>", js_block + "\n</body>", 1)
    elif ".section-pill" not in html and in_page_nav:
        # Sidebar JS exists but subnav JS doesn't — add subnav JS
        last_script = html.rfind("</script>")
        if last_script > 0:
            html = html[:last_script] + "\n" + SUBNAV_JS + "\n" + html[last_script:]

    # Inject dark mode JS if not already present
    if "toggleDarkMode" not in html:
        last_script = html.rfind("</script>")
        if last_script > 0:
            html = html[:last_script] + "\n" + DARKMODE_JS + "\n" + html[last_script:]

    return html


def _render_hub():
    """Render the hub home page HTML from current generated_views state."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM generated_views ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    views = [_row_to_dict(r) for r in rows]

    # Categorize views — split entity pages by entity_type
    prep_docs = [v for v in views if v["view_type"] == "prep_page"]
    contact_pages = [v for v in views if v["view_type"] == "entity_page" and v.get("entity_type") == "contact"]
    project_entity_pages = [v for v in views if v["view_type"] == "entity_page" and v.get("entity_type") == "project"]
    project_briefs = [v for v in views if v["view_type"] == "project_brief"]
    dashboards = [v for v in views if v["view_type"] == "dashboard"]
    tool_pages = [v for v in views if v["view_type"] == "tool_page"]
    pm_reports = [v for v in views if v["view_type"] == "pm_report"]
    project_analyses = [v for v in views if v["view_type"] == "project_analysis"]
    other = [
        v
        for v in views
        if v["view_type"]
        not in ("prep_page", "entity_page", "project_brief", "dashboard", "tool_page", "pm_report", "project_analysis")
    ]

    def _view_card(v, icon="file-text", color="zinc", sub_items=None):
        """Render a single view card, optionally with sub-item links."""
        name = _esc(v["entity_name"] or v["filename"])
        time_ago = _time_ago(v["updated_at"])
        vtype = v["view_type"].replace("_", " ").title()
        href = f"/pages/{_esc(v['filename'])}"
        sub_html = ""
        if sub_items:
            sub_links = ""
            for s in sub_items:
                s_name = s["view_type"].replace("_", " ").title()
                s_href = f"/pages/{_esc(s['filename'])}"
                s_time = _time_ago(s["updated_at"])
                sub_links += f'''
                <a href="{s_href}" class="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 hover:underline">
                    <i data-lucide="brain" class="w-3 h-3"></i>
                    {s_name}
                    <span class="text-zinc-400 ml-auto">{s_time}</span>
                </a>'''
            sub_html = f'<div class="mt-2 pt-2 border-t border-zinc-100 space-y-1">{sub_links}</div>'
        return f"""
        <a href="{href}" class="group bg-white rounded-xl border border-zinc-200 p-4 hover:shadow-md hover:border-zinc-300 transition-all block delight-card delight-hover">
            <div class="flex items-start justify-between mb-2">
                <div class="w-9 h-9 rounded-lg bg-{color}-50 flex items-center justify-center">
                    <i data-lucide="{icon}" class="w-4.5 h-4.5 text-{color}-600"></i>
                </div>
                <span class="text-xs text-zinc-400">{time_ago}</span>
            </div>
            <p class="text-sm font-semibold text-zinc-900 group-hover:text-zinc-700">{name}</p>
            <p class="text-xs text-zinc-400 mt-0.5">{vtype}</p>
        </a>"""

    _sub_icon_map = {
        "pm_report": ("brain", "purple"),
        "project_brief": ("file-text", "zinc"),
        "prep_page": ("clipboard-check", "amber"),
        "project_analysis": ("scan-search", "indigo"),
    }

    def _project_card(v, sub_items=None):
        """Render a project card with optional sub-view links."""
        name = _esc(v["entity_name"] or v["filename"])
        time_ago = _time_ago(v["updated_at"])
        vtype = v["view_type"].replace("_", " ").title()
        href = f"/pages/{_esc(v['filename'])}"
        sub_html = ""
        if sub_items:
            sub_links = ""
            for s in sub_items:
                s_label = s["view_type"].replace("_", " ").title()
                s_href = f"/pages/{_esc(s['filename'])}"
                s_time = _time_ago(s["updated_at"])
                s_icon, s_color = _sub_icon_map.get(s["view_type"], ("file", "purple"))
                sub_links += f'''
                <a href="{s_href}" class="flex items-center gap-1.5 text-xs text-{s_color}-600 hover:text-{s_color}-800 hover:underline py-0.5">
                    <i data-lucide="{s_icon}" class="w-3 h-3 flex-shrink-0"></i>
                    <span>{s_label}</span>
                    <span class="text-zinc-400 ml-auto">{s_time}</span>
                </a>'''
            sub_html = f'<div class="mt-2 pt-2 border-t border-zinc-100 space-y-1">{sub_links}</div>'
        return f"""
        <div class="bg-white rounded-xl border border-zinc-200 p-4 hover:shadow-md hover:border-zinc-300 transition-all delight-card delight-hover">
            <a href="{href}" class="block group">
                <div class="flex items-start justify-between mb-2">
                    <div class="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center">
                        <i data-lucide="folder-open" class="w-4.5 h-4.5 text-green-600"></i>
                    </div>
                    <span class="text-xs text-zinc-400">{time_ago}</span>
                </div>
                <p class="text-sm font-semibold text-zinc-900 group-hover:text-zinc-700">{name}</p>
                <p class="text-xs text-zinc-400 mt-0.5">{vtype}</p>
            </a>
            {sub_html}
        </div>"""

    def _section(title, icon, cards_html):
        if not cards_html:
            return ""
        return f"""
        <section class="mb-8">
            <div class="flex items-center gap-2 mb-3">
                <i data-lucide="{icon}" class="w-4 h-4 text-zinc-400"></i>
                <h2 class="text-sm font-semibold text-zinc-500 uppercase tracking-wide">{title}</h2>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {cards_html}
            </div>
        </section>"""

    # Quick Actions — always shown
    quick_actions = ""

    for d in dashboards:
        quick_actions += f"""
        <a href="/pages/{_esc(d['filename'])}" class="group bg-white rounded-xl border border-zinc-200 p-4 hover:shadow-md hover:border-blue-300 transition-all block delight-card delight-hover">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <i data-lucide="layout-dashboard" class="w-5 h-5 text-blue-600"></i>
                </div>
                <div>
                    <p class="text-sm font-semibold text-zinc-900">Dashboard</p>
                    <p class="text-xs text-zinc-400">Overview &amp; metrics</p>
                </div>
            </div>
        </a>"""

    # Build Prep Docs section
    prep_cards = "\n".join(_view_card(v, "file-text", "amber") for v in prep_docs)

    # Build People section (contacts only)
    people_cards = "\n".join(_view_card(v, "user", "blue") for v in contact_pages)

    # Build Projects section — group entity pages, briefs, and PM reports by entity_id
    # Collect all project-related views by entity_id
    project_groups = {}  # entity_id → {"main": view, "subs": [pm_reports]}
    for v in project_entity_pages:
        eid = v.get("entity_id")
        if eid not in project_groups:
            project_groups[eid] = {"main": v, "subs": []}
        else:
            project_groups[eid]["main"] = v
    for v in project_briefs:
        eid = v.get("entity_id")
        if eid and eid not in project_groups:
            project_groups[eid] = {"main": v, "subs": []}
        elif eid:
            # Only set main if no entity page exists yet
            if not project_groups[eid]["main"]:
                project_groups[eid]["main"] = v
    for v in pm_reports + project_analyses:
        eid = v.get("entity_id")
        if eid and eid in project_groups:
            project_groups[eid]["subs"].append(v)
        elif eid:
            project_groups[eid] = {"main": None, "subs": [v]}
        else:
            # Orphan sub-view (no entity_id) — will be rendered standalone
            if None not in project_groups:
                project_groups[None] = {"main": None, "subs": []}
            project_groups[None]["subs"].append(v)

    project_cards = ""
    for eid, group in project_groups.items():
        if group["main"]:
            project_cards += _project_card(group["main"], group["subs"])
        else:
            # Orphan sub-items without a main project page — render as standalone cards
            for s in group["subs"]:
                project_cards += _view_card(s, "brain", "purple")

    # Build Other section
    other_cards = "\n".join(_view_card(v, "file", "zinc") for v in other)

    # Assemble sections
    sections_html = ""
    sections_html += _section("Prep Docs", "briefcase", prep_cards)
    sections_html += _section("People", "users", people_cards)
    sections_html += _section("Projects", "folder", project_cards)
    sections_html += _section("Other Views", "layers", other_cards)

    has_content = any([prep_docs, contact_pages, project_entity_pages, project_briefs, pm_reports, project_analyses, other])
    empty_state = ""
    if not has_content:
        empty_state = """
        <div class="text-center py-16">
            <div class="w-16 h-16 rounded-2xl bg-zinc-100 flex items-center justify-center mx-auto mb-4">
                <i data-lucide="compass" class="w-8 h-8 text-zinc-400"></i>
            </div>
            <p class="text-zinc-500 mb-1">Your hub will fill up as you use SoY.</p>
            <p class="text-sm text-zinc-400">Try <code class="bg-zinc-100 px-1.5 py-0.5 rounded text-xs">/dashboard</code>, <code class="bg-zinc-100 px-1.5 py-0.5 rounded text-xs">/prep</code>, or <code class="bg-zinc-100 px-1.5 py-0.5 rounded text-xs">/entity-page</code></p>
        </div>"""

    sidebar_html = _build_sidebar(active_page="hub")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <script>(function(){{var s=localStorage.getItem('soy-dark-mode');if(s==='dark'||(s!=='light'&&window.matchMedia('(prefers-color-scheme:dark)').matches)){{document.documentElement.classList.add('dark')}}}})();</script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SoY Hub — Software of You</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{ extend: {{ fontFamily: {{ sans: ['Inter', 'system-ui', 'sans-serif'] }} }} }}
        }}
    </script>
    <style>
        {SIDEBAR_CSS}
        {DARKMODE_CSS}
    </style>
</head>
<body class="bg-zinc-50 text-zinc-900 font-sans antialiased">
    {sidebar_html}

    <main class="lg:ml-60">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        <!-- Header -->
        <div class="flex items-center gap-3 mb-8">
            <div class="w-11 h-11 rounded-xl bg-zinc-900 flex items-center justify-center">
                <i data-lucide="hexagon" class="w-5.5 h-5.5 text-white"></i>
            </div>
            <div>
                <h1 class="text-xl font-bold">Software of You</h1>
                <p class="text-sm text-zinc-400">Your hub</p>
            </div>
        </div>

        <!-- Quick Actions -->
        <section class="mb-8">
            <div class="flex items-center gap-2 mb-3">
                <i data-lucide="zap" class="w-4 h-4 text-zinc-400"></i>
                <h2 class="text-sm font-semibold text-zinc-500 uppercase tracking-wide">Quick Actions</h2>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {quick_actions}
            </div>
        </section>

        {sections_html}
        {empty_state}

      </div>

      <footer class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 pb-8">
          <div class="pt-4 border-t border-zinc-100 text-center">
              <p class="text-xs text-zinc-400">Software of You &middot; Hub &middot; localhost:{DEFAULT_PORT}</p>
          </div>
      </footer>
    </main>

    <script>
        {SIDEBAR_JS}
        {DARKMODE_JS}
        lucide.createIcons();
    </script>
</body>
</html>"""


class SoYHandler(BaseHTTPRequestHandler):
    """Handle hub, page serving, and API requests."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET routes ──────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Health check (lightweight probe for open_page.sh)
        if path == "/health":
            self._send_json({"status": "ok"})
            return

        # Hub home page
        if path == "/":
            self._send_html(_render_hub())
            return

        # Serve shared (client-safe) pages — no sidebar/dark mode injection
        if path.startswith("/share/"):
            filename = path[7:]  # strip "/share/"
            if (
                ".." in filename
                or "/" in filename
                or not filename.endswith(".html")
                or not re.match(r"^[a-zA-Z0-9_\-]+\.html$", filename)
            ):
                self._send_json({"error": "Invalid filename"}, 400)
                return
            filepath = os.path.join(OUTPUT_DIR, "share", filename)
            try:
                with open(filepath, "r") as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json({"error": "Shared page not found. Run /share first."}, 404)
            return

        # Serve pages from output/
        if path.startswith("/pages/"):
            filename = path[7:]  # strip "/pages/"
            # Security: no path traversal, must end in .html
            if (
                ".." in filename
                or "/" in filename
                or not filename.endswith(".html")
                or not re.match(r"^[a-zA-Z0-9_\-]+\.html$", filename)
            ):
                self._send_json({"error": "Invalid filename"}, 400)
                return
            filepath = os.path.join(OUTPUT_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    self._send_html(_inject_sidebar_into_page(f.read(), filename))
            except FileNotFoundError:
                self._send_json({"error": "Page not found"}, 404)
            return

        # API: list registered pages
        if path == "/api/pages":
            conn = _get_db()
            rows = conn.execute(
                "SELECT * FROM generated_views ORDER BY updated_at DESC"
            ).fetchall()
            conn.close()
            self._send_json([_row_to_dict(r) for r in rows])
            return

        # API: list analysis items (optionally filtered by project_id)
        if path == "/api/analysis-items":
            from urllib.parse import parse_qs

            qs = parse_qs(parsed.query)
            conn = _get_db()
            if "project_id" in qs:
                rows = conn.execute(
                    """SELECT ai.*, pa.summary as analysis_summary, pa.created_at as analysis_date
                       FROM project_analysis_items ai
                       JOIN project_analyses pa ON pa.id = ai.analysis_id
                       WHERE ai.project_id = ?
                       ORDER BY ai.category, ai.priority DESC, ai.id""",
                    (qs["project_id"][0],),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT ai.*, pa.summary as analysis_summary, pa.created_at as analysis_date
                       FROM project_analysis_items ai
                       JOIN project_analyses pa ON pa.id = ai.analysis_id
                       ORDER BY ai.created_at DESC, ai.id"""
                ).fetchall()
            conn.close()
            self._send_json([_row_to_dict(r) for r in rows])
            return

        # API: project data for live-updating project pages
        m = re.match(r"^/api/projects/(\d+)$", path)
        if m:
            pid = int(m.group(1))
            conn = _get_db()
            project = conn.execute(
                "SELECT id, name, status, priority FROM projects WHERE id = ?", (pid,)
            ).fetchone()
            if not project:
                conn.close()
                self._send_json({"error": "Not found"}, 404)
                return
            tasks = conn.execute(
                """SELECT id, title, description, status, priority, due_date, completed_at
                   FROM tasks WHERE project_id = ?
                   ORDER BY CASE status
                     WHEN 'in_progress' THEN 1 WHEN 'todo' THEN 2
                     WHEN 'blocked' THEN 3 WHEN 'done' THEN 4 END,
                   due_date ASC NULLS LAST""",
                (pid,),
            ).fetchall()
            health = conn.execute(
                "SELECT * FROM v_project_health WHERE id = ?", (pid,)
            ).fetchone()
            task_stats = {
                "total": health["total_tasks"] if health else 0,
                "todo": health["todo_tasks"] if health else 0,
                "in_progress": health["active_tasks"] if health else 0,
                "done": health["done_tasks"] if health else 0,
                "blocked": health["blocked_tasks"] if health else 0,
                "completion_pct": health["completion_pct"] if health else 0,
            }
            decisions = conn.execute(
                """SELECT id, title, decision, status, decided_at
                   FROM decisions WHERE project_id = ?
                   ORDER BY decided_at DESC""",
                (pid,),
            ).fetchall()
            activity = conn.execute(
                """SELECT action, details, created_at FROM activity_log
                   WHERE entity_type = 'project' AND entity_id = ?
                   ORDER BY created_at DESC LIMIT 20""",
                (pid,),
            ).fetchall()
            conn.close()
            self._send_json({
                "project": _row_to_dict(project),
                "tasks": [_row_to_dict(t) for t in tasks],
                "task_stats": task_stats,
                "decisions": [_row_to_dict(d) for d in decisions],
                "activity": [_row_to_dict(a) for a in activity],
            })
            return

        self._send_json({"error": "Not found"}, 404)

    # ── PATCH routes ────────────────────────────────────────────

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # PATCH task status (for live project page toggle)
        if re.match(r"^/api/tasks/\d+$", path):
            try:
                task_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"error": "Invalid ID"}, 400)
                return
            data = self._read_body()
            new_status = data.get("status")
            if new_status not in ("todo", "in_progress", "done", "blocked"):
                self._send_json({"error": "status must be 'todo', 'in_progress', 'done', or 'blocked'"}, 400)
                return
            conn = _get_db()
            existing = conn.execute(
                "SELECT id, project_id, title, status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not existing:
                conn.close()
                self._send_json({"error": "Not found"}, 404)
                return
            completed_at = "datetime('now')" if new_status == "done" else "NULL"
            conn.execute(
                f"UPDATE tasks SET status = ?, completed_at = {completed_at}, updated_at = datetime('now') WHERE id = ?",
                (new_status, task_id),
            )
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
                   VALUES ('project', ?, 'task_updated', ?, datetime('now'))""",
                (existing["project_id"], json.dumps({"task_id": task_id, "title": existing["title"], "old_status": existing["status"], "new_status": new_status})),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, title, description, status, priority, due_date, completed_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            conn.close()
            self._send_json(_row_to_dict(row))
            return

        # PATCH analysis item (dismiss / un-dismiss)
        if re.match(r"^/api/analysis-items/\d+$", path):
            try:
                item_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json({"error": "Invalid ID"}, 400)
                return
            data = self._read_body()
            new_status = data.get("status")
            if new_status not in ("open", "dismissed"):
                self._send_json({"error": "status must be 'open' or 'dismissed'"}, 400)
                return
            conn = _get_db()
            existing = conn.execute(
                "SELECT id, status FROM project_analysis_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not existing:
                conn.close()
                self._send_json({"error": "Not found"}, 404)
                return
            if existing["status"] == "converted":
                conn.close()
                self._send_json({"error": "Cannot change status of converted item"}, 400)
                return
            conn.execute(
                "UPDATE project_analysis_items SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (new_status, item_id),
            )
            action = "dismissed" if new_status == "dismissed" else "reopened"
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
                   VALUES ('project_analysis_item', ?, ?, ?, datetime('now'))""",
                (item_id, action, json.dumps({"status": new_status})),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM project_analysis_items WHERE id = ?", (item_id,)
            ).fetchone()
            conn.close()
            self._send_json(_row_to_dict(row))
            return

        self._send_json({"error": "Not found"}, 404)

    # ── POST routes ─────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # POST: convert analysis item to task
        if re.match(r"^/api/analysis-items/\d+/convert$", path):
            parts = path.split("/")
            try:
                item_id = int(parts[3])
            except (ValueError, IndexError):
                self._send_json({"error": "Invalid ID"}, 400)
                return
            conn = _get_db()
            item = conn.execute(
                "SELECT * FROM project_analysis_items WHERE id = ?", (item_id,)
            ).fetchone()
            if not item:
                conn.close()
                self._send_json({"error": "Not found"}, 404)
                return
            item = _row_to_dict(item)
            if item["status"] == "converted":
                conn.close()
                self._send_json(
                    {"error": "Already converted", "task_id": item["converted_task_id"]},
                    409,
                )
                return
            # Map priority to task priority
            priority_map = {"critical": "high", "high": "high", "medium": "medium", "low": "low"}
            task_priority = priority_map.get(item["priority"], "medium")
            # Build task description with provenance
            desc_parts = []
            if item["description"]:
                desc_parts.append(item["description"])
            if item["rationale"]:
                desc_parts.append(f"Rationale: {item['rationale']}")
            desc_parts.append(f"[From project analysis — {item['category'].replace('_', ' ')}]")
            desc_parts.append(f"Evidence: {item['grounded_in']}")
            task_desc = "\n\n".join(desc_parts)
            cursor = conn.execute(
                """INSERT INTO tasks (project_id, title, description, priority, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'todo', datetime('now'), datetime('now'))""",
                (item["project_id"], item["title"], task_desc, task_priority),
            )
            task_id = cursor.lastrowid
            conn.execute(
                """UPDATE project_analysis_items
                   SET status = 'converted', converted_task_id = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (task_id, item_id),
            )
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
                   VALUES ('project_analysis_item', ?, 'converted_to_task', ?, datetime('now'))""",
                (item_id, json.dumps({"task_id": task_id, "title": item["title"]})),
            )
            conn.execute(
                """INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
                   VALUES ('task', ?, 'created', ?, datetime('now'))""",
                (task_id, json.dumps({"source": "project_analysis", "analysis_item_id": item_id})),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM project_analysis_items WHERE id = ?", (item_id,)
            ).fetchone()
            conn.close()
            result = _row_to_dict(updated)
            result["task_id"] = task_id
            self._send_json(result, 201)
            return

        if path == "/api/shutdown":
            self._send_json({"status": "shutting down"})
            import threading

            threading.Thread(target=self.server.shutdown).start()
            return

        self._send_json({"error": "Not found"}, 404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    def handle_signal(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    server = HTTPServer(("127.0.0.1", port), SoYHandler)
    print(
        json.dumps({"status": "running", "port": port, "url": f"http://localhost:{port}"})
    )
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
