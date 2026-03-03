#!/usr/bin/env python3
"""Inject an owner comment thread into a local SoY project page.

Adds a comment thread that talks to the same Cloudflare D1 API as the
published page, allowing the owner to read and reply to client comments
directly from the local project page.

Usage:
    python3 shared/inject_owner_comments.py <html_file> --project-id N
"""

import argparse
import json
import os
import re
import sqlite3
import sys


PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")
ENV_PATH = os.path.join(PLUGIN_ROOT, ".env")

# Marker comments for clean stripping by export_page.py
CSS_START = "<!-- SOY-OWNER-COMMENTS-CSS -->"
CSS_END = "<!-- /SOY-OWNER-COMMENTS-CSS -->"
HTML_START = "<!-- SOY-OWNER-COMMENTS -->"
HTML_END = "<!-- /SOY-OWNER-COMMENTS -->"
JS_START = "<!-- SOY-OWNER-COMMENTS-JS -->"
JS_END = "<!-- /SOY-OWNER-COMMENTS-JS -->"


def _load_env():
    """Load config from .env file, falling back to database."""
    config = {}

    # Try .env first
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    config[key.strip()] = value.strip()

    # Fall back to database for missing values
    if not all(k in config for k in ("SOY_API_BASE_URL", "SOY_OWNER_NAME")):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row

            if "SOY_OWNER_NAME" not in config:
                row = conn.execute(
                    "SELECT value FROM user_profile WHERE category='identity' AND key='name'"
                ).fetchone()
                if row:
                    config["SOY_OWNER_NAME"] = row["value"]

            if "SOY_OWNER_EMAIL" not in config:
                row = conn.execute(
                    "SELECT email FROM google_accounts ORDER BY id ASC LIMIT 1"
                ).fetchone()
                if row:
                    config["SOY_OWNER_EMAIL"] = row["email"]

            conn.close()
        except Exception:
            pass

    # Defaults
    config.setdefault("SOY_API_BASE_URL", "https://soy-shared.pages.dev/api")
    config.setdefault("SOY_OWNER_NAME", "Owner")

    return config


def _get_page_token(project_id):
    """Look up the active page token for a project."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT token FROM shared_pages WHERE project_id = ? AND status = 'active' "
            "ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        conn.close()
        return row["token"] if row else None
    except Exception:
        return None


def _get_tasks(project_id):
    """Get tasks for a project from the local DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, title, status FROM tasks WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _inject_task_ids(html, tasks):
    """Add data-task-id attributes to task rows by matching title text."""
    for task in tasks:
        title = task["title"]
        for end in (len(title), 60, 40, 25):
            prefix = title[:end].rstrip()
            if not prefix:
                continue
            prefix_escaped = re.escape(prefix)
            text_match = re.search(prefix_escaped, html)
            if not text_match:
                continue
            search_region = html[:text_match.start()]
            row_pattern = r'<(div|tr|li)\b([^>]*class="[^"]*(?:flex|items|task)[^"]*"[^>]*)>'
            row_matches = list(re.finditer(row_pattern, search_region))
            if not row_matches:
                row_matches = list(re.finditer(r'<(div|tr|li)\b([^>]*)>', search_region))
            if row_matches:
                rm = row_matches[-1]
                if 'data-task-id' in rm.group(2):
                    break
                insert_pos = rm.end() - 1
                attr = f' data-task-id="{task["id"]}" data-task-status="{task["status"]}"'
                html = html[:insert_pos] + attr + html[insert_pos:]
            break
    return html


def _inject_task_section_ids(html):
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


def _strip_existing(html):
    """Remove any previously injected owner comment blocks."""
    html = re.sub(
        rf"{re.escape(CSS_START)}.*?{re.escape(CSS_END)}",
        "", html, flags=re.DOTALL,
    )
    html = re.sub(
        rf"{re.escape(HTML_START)}.*?{re.escape(HTML_END)}",
        "", html, flags=re.DOTALL,
    )
    html = re.sub(
        rf"{re.escape(JS_START)}.*?{re.escape(JS_END)}",
        "", html, flags=re.DOTALL,
    )
    return html


def _build_css():
    """CSS for the owner comment thread."""
    return f"""{CSS_START}
<style>
  .soy-comments {{ max-width: 640px; margin: 2rem auto; padding: 0 1rem; }}
  .soy-comments-header {{ font-size: 0.875rem; font-weight: 600; color: #3f3f46; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }}
  .soy-comments-header svg {{ width: 16px; height: 16px; }}
  .soy-comment-wrap {{ display: flex; flex-direction: column; margin-bottom: 1rem; }}
  .soy-comment-wrap-owner {{ align-items: flex-end; }}
  .soy-comment-wrap-client {{ align-items: flex-start; }}
  .soy-comment-author {{ font-size: 0.6875rem; font-weight: 600; color: #71717a; margin-bottom: 0.1875rem; padding: 0 0.25rem; }}
  .soy-comment {{ max-width: 80%; padding: 0.5rem 0.875rem; border-radius: 1rem; font-size: 0.8125rem; line-height: 1.5; word-wrap: break-word; }}
  .soy-comment-owner {{ background: #18181b; color: #fafafa; border-bottom-right-radius: 0.25rem; }}
  .soy-comment-client {{ background: #f4f4f5; color: #18181b; border-bottom-left-radius: 0.25rem; }}
  .soy-comment-time {{ font-size: 0.625rem; color: #a1a1aa; margin-top: 0.25rem; padding: 0 0.25rem; }}
  .soy-comment-empty {{ text-align: center; color: #a1a1aa; font-size: 0.8125rem; padding: 1.5rem 0; }}
  .soy-comment-input-row {{ display: flex; gap: 0.5rem; margin-top: 1rem; }}
  .soy-comment-input {{ flex: 1; padding: 0.625rem 0.875rem; border: 1px solid #e4e4e7; border-radius: 1rem; font-size: 0.8125rem; font-family: 'Inter', sans-serif; outline: none; transition: border-color 0.15s; }}
  .soy-comment-input:focus {{ border-color: #18181b; }}
  .soy-comment-send {{ background: #18181b; color: #fff; border: none; border-radius: 1rem; padding: 0.625rem 1rem; font-size: 0.8125rem; font-weight: 500; cursor: pointer; font-family: 'Inter', sans-serif; transition: opacity 0.15s; }}
  .soy-comment-send:hover {{ opacity: 0.85; }}
  .soy-comment-send:disabled {{ opacity: 0.4; cursor: not-allowed; }}
  .soy-comment-error {{ text-align: center; color: #a1a1aa; font-size: 0.75rem; padding: 1rem 0; }}
  .soy-comment-error a {{ color: #18181b; text-decoration: underline; }}
  [data-task-id] {{ transition: background-color 0.15s ease; border-radius: 8px; margin: 0 -4px; padding-left: 4px; padding-right: 4px; cursor: pointer; }}
  [data-task-id]:hover {{ background-color: #f4f4f5; }}
  [data-task-id] svg {{ transition: all 0.2s ease; flex-shrink: 0; }}
</style>
{CSS_END}"""


def _build_html():
    """HTML for the comment thread container."""
    return f"""{HTML_START}
<section class="soy-comments" id="soy-owner-comments">
  <div class="soy-comments-header">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
    Comments
  </div>
  <div id="soy-comment-list"></div>
  <div class="soy-comment-input-row">
    <input type="text" class="soy-comment-input" id="soy-comment-input" placeholder="Reply as owner..." autocomplete="off" />
    <button class="soy-comment-send" id="soy-comment-send" onclick="soyPostComment()">Send</button>
  </div>
</section>
{HTML_END}"""


def _build_js(api_base, page_token, owner_name):
    """JS for loading and posting comments."""
    safe_name = owner_name.replace("\\", "\\\\").replace('"', '\\"')
    return f"""{JS_START}
<script>
(function() {{
  const API = "{api_base}";
  const TOKEN = "{page_token}";
  const OWNER = "{safe_name}";

  function fmtTime(ts) {{
    const d = new Date(ts + (ts.includes('Z') ? '' : 'Z'));
    const now = new Date();
    const s = Math.floor((now - d) / 1000);
    const pad = n => String(n).padStart(2, '0');
    const time = pad(d.getHours()) + ':' + pad(d.getMinutes());
    if (s < 86400 && d.getDate() === now.getDate()) return 'Today ' + time;
    if (s < 172800) return 'Yesterday ' + time;
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return months[d.getMonth()] + ' ' + d.getDate() + ', ' + time;
  }}

  function render(comments) {{
    const el = document.getElementById('soy-comment-list');
    if (!comments.length) {{
      el.innerHTML = '<div class="soy-comment-empty">No comments yet</div>';
      return;
    }}
    el.innerHTML = comments.map((c, i) => {{
      const isOwner = c.author_type === 'owner';
      const side = isOwner ? 'owner' : 'client';
      const name = isOwner ? 'You' : (c.author_name || 'Client');
      const prev = comments[i - 1];
      const sameSide = prev && prev.author_type === c.author_type;
      const sameName = sameSide && (prev.author_name || '') === (c.author_name || '');
      const showName = !sameName;
      return '<div class="soy-comment-wrap soy-comment-wrap-' + side + '">'
        + (showName ? '<div class="soy-comment-author">' + name + '</div>' : '')
        + '<div class="soy-comment soy-comment-' + side + '">'
        + c.content.replace(/</g, '&lt;')
        + '</div>'
        + '<div class="soy-comment-time">' + fmtTime(c.created_at) + '</div>'
        + '</div>';
    }}).join('');
    el.scrollTop = el.scrollHeight;
  }}

  function load() {{
    fetch(API + '/comments?page_token=' + TOKEN)
      .then(r => r.json())
      .then(d => render(d.comments || []))
      .catch(() => {{
        document.getElementById('soy-comment-list').innerHTML =
          '<div class="soy-comment-error">Could not load comments. '
          + 'If viewing as a file, open via <a href="http://localhost:8787">localhost:8787</a> instead.</div>';
      }});
  }}

  window.soyPostComment = function() {{
    const input = document.getElementById('soy-comment-input');
    const btn = document.getElementById('soy-comment-send');
    const text = input.value.trim();
    if (!text) return;
    btn.disabled = true;
    fetch(API + '/comments', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        page_token: TOKEN,
        content: text,
        author_name: OWNER,
        author_type: 'owner'
      }})
    }})
    .then(r => r.json())
    .then(() => {{ input.value = ''; load(); }})
    .catch(() => alert('Failed to send — check your connection'))
    .finally(() => {{ btn.disabled = false; }});
  }};

  document.getElementById('soy-comment-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); soyPostComment(); }}
  }});

  // ── Toast ──
  function soyToast(msg) {{
    var t = document.getElementById('soy-toast');
    if (!t) {{
      t = document.createElement('div');
      t.id = 'soy-toast';
      t.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#18181b;color:#fff;padding:12px 20px;border-radius:10px;font-size:0.875rem;z-index:9999;opacity:0;transform:translateY(10px);transition:all 0.3s ease;';
      document.body.appendChild(t);
    }}
    t.textContent = msg;
    t.style.opacity = '1'; t.style.transform = 'translateY(0)';
    setTimeout(function() {{ t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; }}, 2500);
  }}

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

  // Merge In Progress + To Do into a single "Tasks" section
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

  document.querySelectorAll('[data-task-id]').forEach(function(row) {{
    if (row.dataset.taskStatus === 'done') return;
    row.style.cursor = 'pointer';
    row.dataset.checked = 'false';
    row.addEventListener('click', async function(e) {{
      if (e.target.closest('a, button')) return;
      var was = row.dataset.checked === 'true';
      var now = !was;
      row.dataset.checked = String(now);
      await moveTask(row, now, true);
      try {{
        await fetch(API + '/tasks/' + row.dataset.taskId, {{
          method: 'PATCH',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ client_completed: now ? 1 : 0, client_completed_by: OWNER }})
        }});
        soyToast(now ? 'Marked complete' : 'Unmarked');
      }} catch(err) {{
        row.dataset.checked = String(was);
        await moveTask(row, was, true);
        soyToast('Failed to save — try again');
      }}
    }});
  }});

  // Hydrate task states from server
  fetch(API + '/page/' + TOKEN)
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      (d.tasks || []).forEach(function(t) {{
        var row = document.querySelector('[data-task-id="' + t.id + '"]');
        if (row && t.client_completed) {{
          row.dataset.checked = 'true';
          moveTask(row, true, false);
        }}
      }});
    }}).catch(function() {{}});

  load();
}})();
</script>
{JS_END}"""


def inject_owner_comments(html_path, project_id):
    """Inject owner comment thread into an HTML file.

    Returns a result dict with status info.
    """
    config = _load_env()
    page_token = _get_page_token(project_id)

    if not page_token:
        return {"skipped": True, "reason": "no published page for this project"}

    with open(html_path, "r") as f:
        html = f.read()

    # Strip any existing injection first (idempotent)
    html = _strip_existing(html)

    # Inject task IDs so tasks are interactive
    tasks = _get_tasks(project_id)
    if tasks:
        html = _inject_task_ids(html, tasks)
        html = _inject_task_section_ids(html)

    # Inject CSS before </head>
    css_block = _build_css()
    html = html.replace("</head>", css_block + "\n</head>", 1)

    # Inject HTML before <footer
    html_block = _build_html()
    footer_match = re.search(r"<footer\b", html)
    if footer_match:
        html = html[:footer_match.start()] + html_block + "\n" + html[footer_match.start():]
    else:
        # No footer — inject before </main> or </body>
        for tag in ("</main>", "</body>"):
            idx = html.rfind(tag)
            if idx != -1:
                html = html[:idx] + html_block + "\n" + html[idx:]
                break

    # Inject JS before </body>
    js_block = _build_js(
        config["SOY_API_BASE_URL"],
        page_token,
        config.get("SOY_OWNER_NAME", "Owner"),
    )
    html = html.replace("</body>", js_block + "\n</body>", 1)

    with open(html_path, "w") as f:
        f.write(html)

    return {
        "injected": True,
        "file": html_path,
        "page_token": page_token,
        "api_base": config["SOY_API_BASE_URL"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Inject owner comment thread into a local SoY project page"
    )
    parser.add_argument("html_file", help="Path to the HTML file")
    parser.add_argument(
        "--project-id", type=int, required=True, help="Project ID in the database"
    )
    args = parser.parse_args()

    if not os.path.exists(args.html_file):
        print(json.dumps({"error": f"File not found: {args.html_file}"}))
        sys.exit(1)

    result = inject_owner_comments(args.html_file, args.project_id)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
