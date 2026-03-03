#!/usr/bin/env python3
"""Publish a SoY page to Cloudflare for live client interaction.

Takes a clean exported HTML page, injects interactive elements (task checkboxes,
section notes, comment thread, task suggestions), pushes to Cloudflare D1,
and returns a public URL.

Usage:
    python3 shared/publish_page.py publish <input_html> --project-id N --title "..." [--token existing]
    python3 shared/publish_page.py status [token]
    python3 shared/publish_page.py revoke <token>
"""

import json
import os
import re
import secrets
import sqlite3
import sys
import urllib.request
import urllib.error

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_cf_credentials(conn):
    """Get Cloudflare credentials from soy_meta."""
    rows = conn.execute(
        "SELECT key, value FROM soy_meta WHERE key IN "
        "('cf_account_id', 'cf_d1_database_id', 'cf_api_token', 'cf_pages_project')"
    ).fetchall()
    creds = {r["key"]: r["value"] for r in rows}
    required = ["cf_account_id", "cf_d1_database_id", "cf_api_token"]
    missing = [k for k in required if k not in creds]
    if missing:
        return None
    return creds


def _d1_execute(creds, sql, params=None):
    """Execute a SQL statement on D1 via Cloudflare REST API."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{creds['cf_account_id']}"
        f"/d1/database/{creds['cf_d1_database_id']}/query"
    )
    body = {"sql": sql}
    if params:
        body["params"] = params

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {creds['cf_api_token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                return result.get("result", [])
            return {"error": result.get("errors", "Unknown D1 error")}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"D1 API {e.code}: {body[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def _d1_batch(creds, statements):
    """Execute multiple SQL statements on D1 one at a time."""
    errors = []
    for s in statements:
        result = _d1_execute(creds, s["sql"], s.get("params"))
        if isinstance(result, dict) and "error" in result:
            errors.append(result["error"])
    if errors:
        return {"error": "; ".join(errors[:3])}
    return []


# ── HTML Injection ──────────────────────────────────────────────


def inject_data_task_ids(html, tasks):
    """Add data-task-id attributes to task rows by matching title text.

    Finds task title text in the HTML, then walks backward to the nearest
    containing div/tr/li to inject the data attribute. Uses substring
    matching to handle truncated titles.
    """
    for task in tasks:
        title = task["title"]
        # Try progressively shorter prefixes until we find the text
        for end in (len(title), 60, 40, 25):
            prefix = title[:end].rstrip()
            if not prefix:
                continue
            prefix_escaped = re.escape(prefix)
            text_match = re.search(prefix_escaped, html)
            if not text_match:
                continue
            # Found the title text — walk backward to find the task row container
            search_region = html[:text_match.start()]
            # Find the last opening div/tr/li with a class containing flex/items
            # (the task row wrapper), or any div/tr/li as fallback
            row_pattern = r'<(div|tr|li)\b([^>]*class="[^"]*(?:flex|items|task)[^"]*"[^>]*)>'
            row_matches = list(re.finditer(row_pattern, search_region))
            if not row_matches:
                # Fallback: any div/tr/li
                row_matches = list(re.finditer(r'<(div|tr|li)\b([^>]*)>', search_region))
            if row_matches:
                rm = row_matches[-1]
                # Skip if already tagged
                if 'data-task-id' in rm.group(2):
                    break
                insert_pos = rm.end() - 1  # before the closing >
                attr = f' data-task-id="{task["id"]}" data-task-status="{task["status"]}"'
                html = html[:insert_pos] + attr + html[insert_pos:]
            break
    return html


def inject_task_section_ids(html):
    """Add data-task-section to task section containers.

    Finds <!-- In Progress -->, <!-- Todo -->, <!-- Done --> HTML comment
    anchors and tags the next container element with data-task-section
    so the JS can move tasks between sections.
    """
    section_map = [
        ('<!-- In Progress -->', 'in_progress'),
        ('<!-- Todo -->', 'todo'),
        ('<!-- Done -->', 'done'),
    ]
    for comment, section_id in section_map:
        idx = html.find(comment)
        if idx == -1:
            continue
        after = html[idx + len(comment):]
        tag_match = re.search(r'<(div|details)\b([^>]*?)>', after)
        if not tag_match:
            continue
        if 'data-task-section' in tag_match.group(0):
            continue
        abs_pos = idx + len(comment) + tag_match.end() - 1
        html = html[:abs_pos] + f' data-task-section="{section_id}"' + html[abs_pos:]
    return html


def inject_section_ids(html):
    """Add data-section-id to card wrappers identified by heading text."""
    section_idx = [0]

    def _add_section_id(m):
        section_idx[0] += 1
        tag_start = m.group(1)
        rest = m.group(2)
        return f'{tag_start} data-section-id="section-{section_idx[0]}"{rest}'

    # Match card-like divs that contain an h2 or h3 heading
    html = re.sub(
        r'(<div\s+class="(?:bg-white|rounded)[^"]*")'
        r'(\s*>[^<]*<h[23]\b)',
        _add_section_id,
        html,
        flags=re.DOTALL,
    )
    return html


def inject_interactive_js(html, page_token, owner_name=None):
    """Inject the full interactive JavaScript block before </body>."""
    js = _build_interactive_js(page_token, owner_name)
    css = _build_interactive_css()
    inject_block = f"\n{css}\n{js}\n"
    html = html.replace("</body>", f"{inject_block}</body>")
    return html


def inject_comment_thread(html, page_token):
    """Insert a comment thread section before the footer."""
    comment_html = f'''
<!-- Client Comment Thread -->
<div id="soy-comments" class="max-w-5xl mx-auto px-6 mt-8 mb-4">
  <div class="bg-white rounded-xl border border-zinc-200 p-6">
    <h3 class="text-lg font-semibold text-zinc-800 mb-4 flex items-center gap-2">
      <svg class="w-5 h-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
      Comments
    </h3>
    <div id="soy-comment-list" class="space-y-3 mb-4"></div>
    <div class="flex gap-2">
      <input type="text" id="soy-comment-input" placeholder="Add a comment..."
        class="flex-1 px-3 py-2 border border-zinc-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
      <button onclick="soyPostComment()" class="px-4 py-2 bg-zinc-800 text-white text-sm rounded-lg hover:bg-zinc-700 transition-colors">Send</button>
    </div>
  </div>
</div>
'''
    # Insert before footer
    footer_match = re.search(r'<footer\b', html)
    if footer_match:
        html = html[:footer_match.start()] + comment_html + html[footer_match.start():]
    else:
        html = html.replace("</body>", f"{comment_html}</body>")
    return html


def inject_suggest_task_button(html):
    """Add a 'Suggest a task' button in the tasks section."""
    suggest_html = '''
<div class="mt-4 pt-3 border-t border-zinc-100">
  <button onclick="soyShowSuggestForm()" id="soy-suggest-btn"
    class="text-sm text-zinc-500 hover:text-zinc-700 flex items-center gap-1 transition-colors">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
    Suggest a task
  </button>
  <div id="soy-suggest-form" class="hidden mt-3 space-y-2">
    <input type="text" id="soy-suggest-title" placeholder="Task title"
      class="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
    <textarea id="soy-suggest-desc" placeholder="Description (optional)" rows="2"
      class="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
    <div class="flex gap-2">
      <button onclick="soySubmitSuggestion()" class="px-4 py-2 bg-zinc-800 text-white text-sm rounded-lg hover:bg-zinc-700 transition-colors">Submit</button>
      <button onclick="document.getElementById('soy-suggest-form').classList.add('hidden');document.getElementById('soy-suggest-btn').classList.remove('hidden')"
        class="px-4 py-2 text-sm text-zinc-500 hover:text-zinc-700 transition-colors">Cancel</button>
    </div>
  </div>
</div>
'''
    # Insert after the last task-related table/list or after a tasks heading
    # Look for the tasks section end
    task_section = re.search(
        r'(</(?:table|ul|div)>\s*</div>)\s*(?=\s*(?:<div[^>]*data-section-id|<footer|</main|$))',
        html, flags=re.DOTALL
    )
    if task_section:
        insert_pos = task_section.start(1)
        html = html[:insert_pos] + suggest_html + html[insert_pos:]
    return html


def inject_note_buttons(html):
    """Add 'Add note' buttons after section headings."""
    note_btn = (
        '\n<button onclick="soyShowNoteInput(this)" '
        'class="soy-note-btn text-xs text-zinc-400 hover:text-zinc-600 '
        'ml-2 transition-colors">+ Add note</button>'
    )

    # Find sections with data-section-id, then insert note button after the first heading
    def _add_btn(m):
        return m.group(0) + note_btn

    # Match closing h2/h3 tags inside sections that have data-section-id
    html = re.sub(
        r'(data-section-id="[^"]*"[^>]*>[\s\S]*?</h[23]>)',
        _add_btn,
        html,
    )
    return html


def _build_interactive_css():
    """CSS for interactive elements."""
    return '''<style>
  [data-task-id] { transition: background-color 0.15s ease; border-radius: 8px; margin: 0 -4px; padding-left: 4px; padding-right: 4px; }
  [data-task-id]:hover { background-color: #f4f4f5; }
  [data-task-id] svg { transition: all 0.2s ease; flex-shrink: 0; }
  .soy-note-btn { cursor: pointer; }
  .soy-note-input { display: none; }
  .soy-note-input.active { display: block; }
  .soy-note-display { background: #fefce8; border-left: 3px solid #eab308; padding: 8px 12px; margin: 8px 0; border-radius: 6px; font-size: 0.875rem; }
  .soy-comment-wrap { margin-bottom: 0.75rem; display: flex; flex-direction: column; }
  .soy-comment-wrap-client { align-items: flex-start; }
  .soy-comment-wrap-owner { align-items: flex-end; }
  .soy-comment-author { font-size: 0.6875rem; font-weight: 600; color: #71717a; margin-bottom: 2px; padding: 0 4px; }
  .soy-comment-bubble { padding: 8px 12px; border-radius: 12px; font-size: 0.875rem; max-width: 80%; }
  .soy-comment-client { background: #f4f4f5; color: #27272a; border-bottom-left-radius: 3px; }
  .soy-comment-owner { background: #18181b; color: white; border-bottom-right-radius: 3px; }
  .soy-comment-time { font-size: 0.625rem; color: #a1a1aa; margin-top: 2px; padding: 0 4px; }
  .soy-toast { position: fixed; bottom: 24px; right: 24px; background: #18181b; color: white; padding: 12px 20px; border-radius: 10px; font-size: 0.875rem; z-index: 9999; opacity: 0; transform: translateY(10px); transition: all 0.3s ease; }
  .soy-toast.show { opacity: 1; transform: translateY(0); }
</style>'''


def _build_interactive_js(page_token, owner_name=None):
    """Build the full interactive JS block."""
    safe_owner_name = (owner_name or "").replace('"', '\\"')
    return f'''<script>
(function() {{
  const PAGE_TOKEN = "{page_token}";
  const API_BASE = window.location.origin + "/api";
  const OWNER_NAME = "{safe_owner_name}";

  // Detect if current user is the page owner via email match
  // Session email is injected by the Worker for returning visitors;
  // auth email is stored by the auth gate on first visit
  const ownerEmail = window.__SOY_OWNER_EMAIL__ || "";
  const authEmail = window.__SOY_SESSION_EMAIL__ || localStorage.getItem("soy-auth-email") || "";
  const isOwner = ownerEmail && authEmail && ownerEmail === authEmail.toLowerCase();

  let clientName = localStorage.getItem("soy-client-name-" + PAGE_TOKEN);

  if (isOwner && OWNER_NAME) {{
    // Owner detected — use their name, no prompt needed
    clientName = OWNER_NAME;
    localStorage.setItem("soy-client-name-" + PAGE_TOKEN, clientName);
  }} else if (!clientName) {{
    // Prompt for name on first visit
    clientName = prompt("Welcome! What's your name?") || "Client";
    localStorage.setItem("soy-client-name-" + PAGE_TOKEN, clientName);
  }}

  // ── Toast ──
  window.soyToast = function(msg) {{
    let t = document.getElementById("soy-toast");
    if (!t) {{
      t = document.createElement("div");
      t.id = "soy-toast";
      t.className = "soy-toast";
      document.body.appendChild(t);
    }}
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2500);
  }};

  // ── Task Move Between Sections ──
  var ICON_CHECK = '<polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>';
  var ICON_SQUARE = '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>';
  var ICON_CIRCLE = '<circle cx="12" cy="12" r="10"></circle>';

  function getTaskList(s) {{ return s.querySelector('.space-y-2'); }}

  function findCountEl(s) {{
    if (s.dataset.taskSection === 'done') return s.querySelector('summary');
    for (var i = 0; i < s.children.length; i++) if (s.children[i].tagName === 'P') return s.children[i];
    return null;
  }}

  function updateSectionUI(s) {{
    if (!s) return;
    var c = s.querySelectorAll('[data-task-id]').length;
    var el = findCountEl(s);
    if (el) el.innerHTML = el.innerHTML.replace(/\(\d+\)/, '(' + c + ')');
    if (s.dataset.taskSection === 'done') {{
      s.style.display = c > 0 ? '' : 'none';
      if (c > 0) s.open = true;
    }} else {{
      s.style.display = c > 0 ? '' : 'none';
    }}
  }}

  function styleAsDone(row) {{
    var icon = row.querySelector('svg');
    if (icon) {{ icon.innerHTML = ICON_CHECK; icon.classList.remove('text-blue-500', 'text-zinc-300'); icon.classList.add('text-emerald-500'); }}
    var ps = row.querySelectorAll('p');
    if (ps[0]) {{ ps[0].style.textDecoration = 'line-through'; ps[0].style.opacity = '0.5'; }}
    if (ps[1]) ps[1].style.display = 'none';
  }}

  function styleAsActive(row) {{
    var icon = row.querySelector('svg');
    if (icon) {{
      icon.innerHTML = ICON_SQUARE; icon.classList.remove('text-emerald-500', 'text-blue-500'); icon.classList.add('text-zinc-300');
    }}
    var ps = row.querySelectorAll('p');
    if (ps[0]) {{ ps[0].className = 'text-sm font-medium text-zinc-800'; ps[0].style.textDecoration = ''; ps[0].style.opacity = ''; }}
    if (ps[1]) ps[1].style.display = '';
  }}

  function moveTask(row, toDone, animate) {{
    var src = row.closest('[data-task-section]');
    if (!src) {{ if (toDone) styleAsDone(row); else styleAsActive(row); return Promise.resolve(); }}
    if (!row.dataset.originalSection) row.dataset.originalSection = src.dataset.taskSection;
    var tgt = document.querySelector('[data-task-section="' + (toDone ? 'done' : row.dataset.originalSection) + '"]');
    if (!tgt) {{ if (toDone) styleAsDone(row); else styleAsActive(row); return Promise.resolve(); }}
    var list = getTaskList(tgt);
    if (!list) {{ if (toDone) styleAsDone(row); else styleAsActive(row); return Promise.resolve(); }}
    function doMove() {{
      if (toDone) styleAsDone(row); else styleAsActive(row);
      list.appendChild(row);
      updateSectionUI(src);
      updateSectionUI(tgt);
    }}
    if (!animate) {{ doMove(); return Promise.resolve(); }}
    return new Promise(function(resolve) {{
      row.style.transition = 'opacity 150ms ease, transform 150ms ease';
      row.style.opacity = '0'; row.style.transform = 'translateY(-8px)';
      setTimeout(function() {{
        doMove();
        row.style.opacity = '0'; row.style.transform = 'translateY(8px)';
        row.offsetHeight;
        row.style.transition = 'opacity 150ms ease, transform 150ms ease';
        row.style.opacity = '1'; row.style.transform = 'translateY(0)';
        setTimeout(function() {{ row.style.transition = ''; row.style.transform = ''; resolve(); }}, 150);
      }}, 150);
    }});
  }}

  // Merge In Progress + To Do into a single "Tasks" section for client view
  (function() {{
    var sections = document.querySelectorAll('[data-task-section="in_progress"], [data-task-section="todo"]');
    if (sections.length < 1) return;
    var target = sections[0];
    var targetList = getTaskList(target);
    if (!targetList) return;
    for (var i = 1; i < sections.length; i++) {{
      var srcList = getTaskList(sections[i]);
      if (srcList) while (srcList.firstChild) targetList.appendChild(srcList.firstChild);
      sections[i].style.display = 'none';
      sections[i].removeAttribute('data-task-section');
    }}
    target.dataset.taskSection = 'active';
    var header = findCountEl(target);
    if (header) {{
      var count = target.querySelectorAll('[data-task-id]').length;
      header.className = 'text-xs font-semibold text-zinc-600 uppercase tracking-wide mb-2';
      header.textContent = 'Tasks (' + count + ')';
    }}
    // Normalize all active task styling to uniform appearance
    target.querySelectorAll('[data-task-id]').forEach(function(r) {{
      if (r.dataset.taskStatus === 'done') return;
      var icon = r.querySelector('i[data-lucide], svg');
      if (icon) {{
        if (icon.tagName === 'I') icon.setAttribute('data-lucide', 'square');
        else icon.innerHTML = ICON_SQUARE;
        icon.classList.remove('text-blue-500', 'text-emerald-500');
        icon.classList.add('text-zinc-300');
      }}
      var ps = r.querySelectorAll('p');
      if (ps[0]) ps[0].className = 'text-sm font-medium text-zinc-800';
    }});
  }})();

  document.querySelectorAll("[data-task-id]").forEach(function(row) {{
    if (row.dataset.taskStatus === "done") return;
    row.style.cursor = "pointer";
    row.dataset.checked = "false";
    row.addEventListener("click", async function(e) {{
      if (e.target.closest("a, button")) return;
      var was = row.dataset.checked === "true";
      var now = !was;
      row.dataset.checked = String(now);
      await moveTask(row, now, true);
      try {{
        await fetch(API_BASE + "/tasks/" + row.dataset.taskId, {{
          method: "PATCH",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ client_completed: now ? 1 : 0, client_completed_by: clientName }})
        }});
        soyToast(now ? "Marked complete" : "Unmarked");
      }} catch(err) {{
        row.dataset.checked = String(was);
        await moveTask(row, was, true);
        soyToast("Failed to save — try again");
      }}
    }});
  }});

  // ── Hydrate from server ──
  async function hydrate() {{
    try {{
      const resp = await fetch(API_BASE + "/page/" + PAGE_TOKEN);
      const data = await resp.json();

      // Hydrate task states — move client-completed tasks to Done section
      (data.tasks || []).forEach(t => {{
        const row = document.querySelector('[data-task-id="' + t.id + '"]');
        if (!row) return;
        if (t.client_completed) {{
          row.dataset.checked = "true";
          moveTask(row, true, false);
        }}
      }});

      // Hydrate notes
      (data.notes || []).forEach(n => {{
        const section = document.querySelector('[data-section-id="' + n.section_id + '"]');
        if (!section) return;
        const noteDiv = document.createElement("div");
        noteDiv.className = "soy-note-display";
        noteDiv.innerHTML = '<strong>' + escHtml(n.author_name) + ':</strong> ' + escHtml(n.content);
        const heading = section.querySelector("h2, h3");
        if (heading) heading.parentNode.insertBefore(noteDiv, heading.nextSibling);
      }});

      // Hydrate comments
      renderComments(data.comments || []);
    }} catch(e) {{ /* Use page as-is if hydration fails */ }}
  }}

  function escHtml(s) {{ const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }}

  // ── Comments ──
  function fmtTime(ts) {{
    var d = new Date(ts + (ts.indexOf("Z") >= 0 ? "" : "Z"));
    var now = new Date();
    var s = Math.floor((now - d) / 1000);
    var pad = function(n) {{ return n < 10 ? "0" + n : "" + n; }};
    var time = pad(d.getHours()) + ":" + pad(d.getMinutes());
    if (s < 86400 && d.getDate() === now.getDate()) return "Today " + time;
    if (s < 172800) return "Yesterday " + time;
    var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return months[d.getMonth()] + " " + d.getDate() + ", " + time;
  }}

  function renderComments(comments) {{
    const list = document.getElementById("soy-comment-list");
    if (!list) return;
    list.innerHTML = "";
    comments.forEach(function(c, i) {{
      const isOwner = c.author_type === "owner";
      const side = isOwner ? "owner" : "client";
      const name = c.author_name || (isOwner ? "Owner" : "Client");
      const prev = comments[i - 1];
      const sameName = prev && prev.author_type === c.author_type && (prev.author_name || "") === (c.author_name || "");

      const wrap = document.createElement("div");
      wrap.className = "soy-comment-wrap soy-comment-wrap-" + side;

      if (!sameName) {{
        const nameEl = document.createElement("div");
        nameEl.className = "soy-comment-author";
        nameEl.textContent = name;
        wrap.appendChild(nameEl);
      }}

      const bubble = document.createElement("div");
      bubble.className = "soy-comment-bubble soy-comment-" + side;
      bubble.textContent = c.content;
      wrap.appendChild(bubble);

      const timeEl = document.createElement("div");
      timeEl.className = "soy-comment-time";
      timeEl.textContent = fmtTime(c.created_at);
      wrap.appendChild(timeEl);

      list.appendChild(wrap);
    }});
    list.scrollTop = list.scrollHeight;
  }}

  window.soyPostComment = async function() {{
    const input = document.getElementById("soy-comment-input");
    const content = input.value.trim();
    if (!content) return;
    input.value = "";
    try {{
      await fetch(API_BASE + "/comments", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ page_token: PAGE_TOKEN, content, author_name: clientName, author_type: isOwner ? "owner" : "client" }})
      }});
      // Refresh comments
      const resp = await fetch(API_BASE + "/comments?page_token=" + PAGE_TOKEN);
      const data = await resp.json();
      renderComments(data.comments || []);
      soyToast("Comment posted");
    }} catch(e) {{ soyToast("Failed to post comment"); }}
  }};

  // ── Notes ──
  window.soyShowNoteInput = function(btn) {{
    let container = btn.nextElementSibling;
    if (container && container.classList.contains("soy-note-input")) {{
      container.classList.toggle("active");
      return;
    }}
    container = document.createElement("div");
    container.className = "soy-note-input active";
    container.innerHTML = '<div class="flex gap-2 mt-2"><input type="text" placeholder="Your note..." class="flex-1 px-3 py-1.5 border border-zinc-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" /><button class="px-3 py-1.5 bg-zinc-800 text-white text-sm rounded-lg hover:bg-zinc-700">Save</button></div>';
    btn.parentNode.insertBefore(container, btn.nextSibling);
    const saveBtn = container.querySelector("button");
    const noteInput = container.querySelector("input");
    saveBtn.onclick = async function() {{
      const content = noteInput.value.trim();
      if (!content) return;
      const section = btn.closest("[data-section-id]");
      const sectionId = section ? section.dataset.sectionId : "unknown";
      try {{
        await fetch(API_BASE + "/notes", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ page_token: PAGE_TOKEN, section_id: sectionId, content, author_name: clientName }})
        }});
        const noteDiv = document.createElement("div");
        noteDiv.className = "soy-note-display";
        noteDiv.innerHTML = '<strong>' + escHtml(clientName) + ':</strong> ' + escHtml(content);
        container.parentNode.insertBefore(noteDiv, container);
        container.classList.remove("active");
        noteInput.value = "";
        soyToast("Note saved");
      }} catch(e) {{ soyToast("Failed to save note"); }}
    }};
  }};

  // ── Suggestions ──
  window.soyShowSuggestForm = function() {{
    document.getElementById("soy-suggest-btn").classList.add("hidden");
    document.getElementById("soy-suggest-form").classList.remove("hidden");
  }};

  window.soySubmitSuggestion = async function() {{
    const title = document.getElementById("soy-suggest-title").value.trim();
    const desc = document.getElementById("soy-suggest-desc").value.trim();
    if (!title) {{ soyToast("Title is required"); return; }}
    try {{
      await fetch(API_BASE + "/suggestions", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ page_token: PAGE_TOKEN, title, description: desc || null, suggested_by: clientName }})
      }});
      document.getElementById("soy-suggest-title").value = "";
      document.getElementById("soy-suggest-desc").value = "";
      document.getElementById("soy-suggest-form").classList.add("hidden");
      document.getElementById("soy-suggest-btn").classList.remove("hidden");
      soyToast("Suggestion submitted — thanks!");
    }} catch(e) {{ soyToast("Failed to submit suggestion"); }}
  }};

  // Enter key for comment input
  document.addEventListener("DOMContentLoaded", function() {{
    const ci = document.getElementById("soy-comment-input");
    if (ci) ci.addEventListener("keydown", function(e) {{ if (e.key === "Enter") soyPostComment(); }});
  }});

  // Hydrate on load
  hydrate();
}})();
</script>'''


# ── Subcommands ─────────────────────────────────────────────────


def cmd_publish(args):
    """Publish a page to Cloudflare."""
    if len(args) < 1:
        print(json.dumps({"error": "Usage: publish <input_html> --project-id N --title '...' [--email addr]"}))
        sys.exit(1)

    input_file = args[0]
    project_id = None
    title = None
    token = None
    email = None
    owner_email_override = None

    i = 1
    while i < len(args):
        if args[i] == "--project-id" and i + 1 < len(args):
            project_id = int(args[i + 1])
            i += 2
        elif args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]
            i += 2
        elif args[i] == "--token" and i + 1 < len(args):
            token = args[i + 1]
            i += 2
        elif args[i] == "--email" and i + 1 < len(args):
            email = args[i + 1].strip().lower()
            i += 2
        elif args[i] == "--owner-email" and i + 1 < len(args):
            owner_email_override = args[i + 1].strip().lower()
            i += 2
        else:
            i += 1

    if not os.path.exists(input_file):
        print(json.dumps({"error": f"File not found: {input_file}"}))
        sys.exit(1)

    if not project_id:
        print(json.dumps({"error": "--project-id is required"}))
        sys.exit(1)

    conn = _get_db()

    # Get Cloudflare credentials
    creds = _get_cf_credentials(conn)
    if not creds:
        print(json.dumps({"error": "Cloudflare not configured. Run /publish setup first."}))
        sys.exit(1)

    # Get project tasks
    tasks = conn.execute(
        "SELECT id, title, status, priority FROM tasks WHERE project_id = ? ORDER BY sort_order, id",
        (project_id,),
    ).fetchall()
    tasks = [dict(t) for t in tasks]

    # Get user name
    user_row = conn.execute(
        "SELECT value FROM user_profile WHERE category='identity' AND key='name'"
    ).fetchone()
    owner_name = user_row["value"] if user_row else "Software of You"

    # Read clean HTML
    with open(input_file, "r") as f:
        html = f.read()

    if not title:
        title_match = re.search(r"<title>([^<]*)</title>", html)
        title = title_match.group(1) if title_match else os.path.basename(input_file)

    # Determine token — reuse existing or generate new
    if not token:
        existing = conn.execute(
            "SELECT token FROM shared_pages WHERE project_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if existing:
            token = existing["token"]
        else:
            token = secrets.token_urlsafe(12)

    # Get owner email: explicit override > soy_meta > google_accounts
    if owner_email_override:
        owner_email = owner_email_override
    else:
        email_row = conn.execute(
            "SELECT value FROM soy_meta WHERE key = 'google_email'"
        ).fetchone()
        if email_row:
            owner_email = email_row["value"]
        else:
            email_row = conn.execute(
                "SELECT email FROM google_accounts ORDER BY id ASC LIMIT 1"
            ).fetchone()
            owner_email = email_row["email"] if email_row else None

    # ── Inject interactive elements ──
    html = inject_section_ids(html)
    html = inject_data_task_ids(html, tasks)
    html = inject_task_section_ids(html)
    html = inject_note_buttons(html)
    html = inject_suggest_task_button(html)
    html = inject_comment_thread(html, token)
    html = inject_interactive_js(html, token, owner_name)

    # ── Push to D1 ──
    # Upsert the page
    page_result = _d1_execute(
        creds,
        "INSERT INTO pages (token, project_id, title, html, owner_name, owner_email, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(token) DO UPDATE SET title=excluded.title, html=excluded.html, "
        "owner_name=excluded.owner_name, owner_email=excluded.owner_email, updated_at=datetime('now')",
        [token, project_id, title, html, owner_name, owner_email],
    )
    if isinstance(page_result, dict) and "error" in page_result:
        print(json.dumps({"error": f"Failed to push page: {page_result['error']}"}))
        sys.exit(1)

    # Push tasks
    task_statements = []
    for t in tasks:
        task_statements.append({
            "sql": (
                "INSERT INTO tasks (id, page_token, title, status, priority) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
                "status=excluded.status, priority=excluded.priority, updated_at=datetime('now')"
            ),
            "params": [t["id"], token, t["title"], t["status"], t["priority"]],
        })

    if task_statements:
        batch_result = _d1_batch(creds, task_statements)
        if isinstance(batch_result, dict) and "error" in batch_result:
            print(json.dumps({"error": f"Failed to push tasks: {batch_result['error']}"}))
            sys.exit(1)

    # ── Email-gated access control ──
    shared_with = None
    if email:
        access_result = _d1_execute(
            creds,
            "INSERT INTO page_access (page_token, email) VALUES (?, ?) "
            "ON CONFLICT(page_token, email) DO NOTHING",
            [token, email],
        )
        if isinstance(access_result, dict) and "error" in access_result:
            # Non-fatal: page is published, access row just didn't land
            sys.stderr.write(f"Warning: failed to set access control: {access_result['error']}\n")
        else:
            shared_with = email

    # Determine published URL
    pages_project = creds.get("cf_pages_project", "soy-shared")
    published_url = f"https://{pages_project}.pages.dev/p/{token}"

    # ── Record locally ──
    conn.execute(
        "INSERT INTO shared_pages (token, project_id, source_filename, title, published_url, status, last_published_at) "
        "VALUES (?, ?, ?, ?, ?, 'active', datetime('now')) "
        "ON CONFLICT(token) DO UPDATE SET title=excluded.title, source_filename=excluded.source_filename, "
        "published_url=excluded.published_url, last_published_at=datetime('now'), updated_at=datetime('now')",
        (token, project_id, os.path.basename(input_file), title, published_url),
    )
    conn.execute(
        "INSERT INTO shared_page_sync_log (shared_page_id, direction, items_synced, details) "
        "VALUES ((SELECT id FROM shared_pages WHERE token = ?), 'push', ?, ?)",
        (token, 1 + len(tasks), json.dumps({"page": True, "tasks": len(tasks)})),
    )
    conn.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
        "VALUES ('shared_page', (SELECT id FROM shared_pages WHERE token = ?), 'published', ?, datetime('now'))",
        (token, json.dumps({"title": title, "url": published_url, "tasks": len(tasks)})),
    )
    # ── Record local access control ──
    if shared_with:
        conn.execute(
            "INSERT OR IGNORE INTO shared_page_access (shared_page_id, email) "
            "VALUES ((SELECT id FROM shared_pages WHERE token = ?), ?)",
            (token, shared_with),
        )

    conn.commit()
    conn.close()

    result = {
        "url": published_url,
        "token": token,
        "title": title,
        "tasks_pushed": len(tasks),
    }
    if shared_with:
        result["shared_with"] = shared_with
    print(json.dumps(result))


def cmd_status(args):
    """Show status of published pages."""
    conn = _get_db()
    token = args[0] if args else None

    if token:
        page = conn.execute(
            "SELECT * FROM shared_pages WHERE token = ?", (token,)
        ).fetchone()
        if not page:
            print(json.dumps({"error": f"No page found with token: {token}"}))
            sys.exit(1)
        print(json.dumps(dict(page)))
    else:
        pages = conn.execute(
            "SELECT token, project_id, title, published_url, status, last_published_at, last_synced_at "
            "FROM shared_pages ORDER BY last_published_at DESC"
        ).fetchall()
        print(json.dumps({"pages": [dict(p) for p in pages]}))

    conn.close()


def cmd_revoke(args):
    """Revoke a published page."""
    if not args:
        print(json.dumps({"error": "Usage: revoke <token>"}))
        sys.exit(1)

    token = args[0]
    conn = _get_db()

    page = conn.execute(
        "SELECT id, title FROM shared_pages WHERE token = ?", (token,)
    ).fetchone()
    if not page:
        print(json.dumps({"error": f"No page found with token: {token}"}))
        sys.exit(1)

    # Remove from D1
    creds = _get_cf_credentials(conn)
    if creds:
        _d1_execute(creds, "DELETE FROM pages WHERE token = ?", [token])
        _d1_execute(creds, "DELETE FROM tasks WHERE page_token = ?", [token])
        _d1_execute(creds, "DELETE FROM notes WHERE page_token = ?", [token])
        _d1_execute(creds, "DELETE FROM comments WHERE page_token = ?", [token])
        _d1_execute(creds, "DELETE FROM suggestions WHERE page_token = ?", [token])

    # Update local status
    conn.execute(
        "UPDATE shared_pages SET status = 'revoked', updated_at = datetime('now') WHERE token = ?",
        (token,),
    )
    conn.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
        "VALUES ('shared_page', ?, 'revoked', ?, datetime('now'))",
        (page["id"], json.dumps({"title": page["title"], "token": token})),
    )
    conn.commit()
    conn.close()

    print(json.dumps({"revoked": True, "token": token, "title": page["title"]}))


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: publish_page.py <publish|status|revoke> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "publish":
        cmd_publish(rest)
    elif command == "status":
        cmd_status(rest)
    elif command == "revoke":
        cmd_revoke(rest)
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
