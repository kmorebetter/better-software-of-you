#!/usr/bin/env python3
"""Local Telegram bot for Software of You.

Runs locally via long-polling. Uses `claude -p` (Claude Code CLI) for AI
responses and `claude -p --dangerously-skip-permissions` for autonomous dev
sessions. Reads/writes the local SoY SQLite database directly.

Prerequisites:
    - Python 3.8+
    - Claude Code CLI (`claude`) in PATH with active subscription
    - git (for dev sessions)
    - vercel CLI (optional, for preview deploys)
    - TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env

Usage:
    python3 shared/telegram_bot.py
"""

import contextlib
import json
import os
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DB_PATH = os.path.join(PLUGIN_ROOT, "data", "soy.db")

# Load .env if present
ENV_PATH = os.path.join(PLUGIN_ROOT, ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                # Strip surrounding quotes (single or double)
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                os.environ.setdefault(k.strip(), v)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = os.environ.get("TELEGRAM_OWNER_ID", "")

# ── Constants ──

# Telegram
POLL_TIMEOUT = 30
MAX_MESSAGE_LEN = 4096
ALLOWED_CALLBACK_ACTIONS = {"approve", "reject"}

# Claude
DEFAULT_MODEL = "sonnet"
ALLOWED_MODELS = {"sonnet", "opus", "haiku"}
CLAUDE_TIMEOUT = 120

# Sessions & timeouts
SESSION_TIMEOUT_HOURS = 4
DEV_SESSION_TIMEOUT = 600  # 10 minutes
NEW_PROJECT_TIMEOUT = 1200  # 20 minutes
DEV_SESSION_MAX_ACTIVE = 3
DEPLOY_TIMEOUT = 180  # 3 minutes
CONFIRMATION_TIMEOUT = 120  # seconds

# Workspace & files
DEV_BRANCH_PREFIX = "dev/"
WORKSPACE_BASE = os.environ.get("SOY_WORKSPACE_ROOT", "~/wkspaces")
INBOX_PROJECT_NAME = "Telegram Inbox"
ERROR_LOG_MAX = 50
TEMP_FILE_MAX_AGE = 86400  # 24 hours
TASK_DISPLAY_LIMIT = 30

# Icons
STATUS_ICONS = {
    "running": "🔄", "completed": "✅", "failed": "❌",
    "timeout": "⏰", "killed": "💀",
}
DEPLOY_ICONS = {
    "deploying": "🚀", "deployed": "🌐", "deploy_failed": "⚠️",
}
REVIEW_ICONS = {
    "pending": "⏳", "approved": "✅", "rejected": "🗑",
}
PRIORITY_ICONS = {
    "urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪",
}


class TelegramBot:
    def __init__(self):
        self.running = False
        self.start_time = None
        self.message_count = 0
        self.last_claude_call = None
        self.current_session_id = None
        self.active_dev_sessions = {}  # session_id -> {process, stdout_file, started_at, chat_id, ...}
        self.active_deploys = {}  # session_id -> {process, stdout_file, started_at, chat_id, ...}
        self.workspace_locks = set()  # workspace paths currently in use (dev, approve, reject)
        self.pending_confirmations = {}  # chat_id -> {action, data, expires_at}

    # ── Telegram API ──

    def _api(self, method, data=None):
        """Call Telegram Bot API."""
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        if data:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        else:
            req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return {"ok": False, "description": f"HTTP {e.code}: {body[:300]}"}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def send_message(self, chat_id, text):
        """Send a message, splitting at paragraph boundaries if too long."""
        chunks = self._chunk_text(text)
        for chunk in chunks:
            result = self._api("sendMessage", {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            })
            # Retry without Markdown if parse fails
            if not result.get("ok"):
                self._api("sendMessage", {
                    "chat_id": chat_id,
                    "text": chunk,
                })

    def send_message_with_buttons(self, chat_id, text, buttons):
        """Send a message with inline keyboard buttons.

        buttons: list of [{"text": "Label", "callback_data": "action:data"}, ...]
        Each inner list is a row of buttons.
        """
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": buttons},
        }
        result = self._api("sendMessage", payload)
        if not result.get("ok"):
            # Retry without Markdown
            del payload["parse_mode"]
            self._api("sendMessage", payload)

    def _answer_callback(self, callback_query_id, text=None):
        """Acknowledge a callback query (dismisses the loading spinner)."""
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        self._api("answerCallbackQuery", data)

    @staticmethod
    def _approve_reject_buttons(session_id):
        """Build inline keyboard buttons for approve/reject actions."""
        return [[
            {"text": "✅ Approve", "callback_data": f"approve:{session_id}"},
            {"text": "🗑 Reject", "callback_data": f"reject:{session_id}"},
        ]]

    def send_typing(self, chat_id):
        """Send typing indicator."""
        self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    @staticmethod
    def _chunk_text(text):
        """Split text at paragraph boundaries for Telegram's 4096 char limit."""
        if len(text) <= MAX_MESSAGE_LEN:
            return [text]
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= MAX_MESSAGE_LEN:
                chunks.append(remaining)
                break
            # Find last paragraph break within limit
            split_idx = remaining.rfind("\n\n", 0, MAX_MESSAGE_LEN)
            if split_idx < MAX_MESSAGE_LEN // 2:
                split_idx = remaining.rfind("\n", 0, MAX_MESSAGE_LEN)
            if split_idx < MAX_MESSAGE_LEN // 2:
                split_idx = MAX_MESSAGE_LEN
            chunks.append(remaining[:split_idx])
            remaining = remaining[split_idx:].lstrip()
        return chunks

    # ── Database ──

    @contextlib.contextmanager
    def _db(self):
        """Context manager for database connections. Rolls back on exception, always closes."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _extract_model_flag(args):
        """Extract --model flag from args. Returns (model, cleaned_args)."""
        model = DEFAULT_MODEL
        if "--model" in args:
            model_match = re.search(r'--model\s+(\w+)', args)
            if model_match:
                model = model_match.group(1)
                args = re.sub(r'--model\s+\w+\s*', '', args).strip()
        return model, args

    @staticmethod
    def _find_session_by_prefix(conn, prefix):
        """Find a dev session by ID prefix. Returns (Row, None) or (None, error_msg)."""
        rows = conn.execute(
            "SELECT * FROM telegram_dev_sessions WHERE SUBSTR(session_id, 1, ?) = ?",
            (len(prefix), prefix),
        ).fetchall()
        if len(rows) == 1:
            return rows[0], None
        if len(rows) > 1:
            ids = ", ".join(f"`{r['session_id']}`" for r in rows)
            return None, f"Ambiguous prefix — matches {len(rows)} sessions: {ids}\nUse more characters to narrow it down."
        return None, None

    @staticmethod
    def _format_duration(seconds):
        """Format seconds as 'Xm Ys' or 'Ys'."""
        mins, secs = divmod(int(seconds), 60)
        return f"{mins}m {secs}s" if mins else f"{secs}s"

    def _log_error(self, error_msg, stack=None, user_msg=None):
        """Log error to telegram_bot_errors, keep last ERROR_LOG_MAX."""
        try:
            with self._db() as conn:
                conn.execute(
                    "INSERT INTO telegram_bot_errors (error_message, error_stack, user_message_preview) "
                    "VALUES (?, ?, ?)",
                    (str(error_msg)[:500], (stack or "")[:500], (user_msg or "")[:100]),
                )
                conn.execute(
                    "DELETE FROM telegram_bot_errors WHERE id NOT IN "
                    f"(SELECT id FROM telegram_bot_errors ORDER BY created_at DESC LIMIT {ERROR_LOG_MAX})"
                )
                conn.commit()
        except Exception:
            pass

    # ── Session Management ──

    def _get_or_create_session(self):
        """Get active session or create new one."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id, message_count FROM telegram_bot_sessions "
                "WHERE last_message_at > datetime('now', ? || ' hours') "
                "ORDER BY last_message_at DESC LIMIT 1",
                (f"-{SESSION_TIMEOUT_HOURS}",),
            ).fetchone()

            if row:
                session_id = row["id"]
                conn.execute(
                    "UPDATE telegram_bot_sessions SET last_message_at = datetime('now'), "
                    "message_count = message_count + 1 WHERE id = ?",
                    (session_id,),
                )
            else:
                session_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO telegram_bot_sessions (id) VALUES (?)",
                    (session_id,),
                )
            conn.commit()
        self.current_session_id = session_id
        return session_id

    def _save_message(self, session_id, role, content, telegram_msg_id=None):
        """Save message to conversation history."""
        with self._db() as conn:
            conn.execute(
                "INSERT INTO telegram_conversations (session_id, role, content, telegram_message_id) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, telegram_msg_id),
            )
            conn.commit()

    def _get_history(self, session_id, limit=20):
        """Get recent conversation history for context."""
        with self._db() as conn:
            rows = conn.execute(
                "SELECT role, content FROM telegram_conversations "
                "WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        # Reverse to chronological
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── Context Building ──

    def _build_system_prompt(self):
        """Build system prompt with live SoY data."""
        with self._db() as conn:
            # Owner name
            owner_row = conn.execute(
                "SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name'"
            ).fetchone()
            owner_name = owner_row["value"] if owner_row else "there"

            # Projects
            projects = conn.execute(
                "SELECT p.name, p.status, c.name as client, "
                "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') as open_tasks, "
                "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'done') as done_tasks "
                "FROM projects p LEFT JOIN contacts c ON c.id = p.client_id "
                "WHERE p.status IN ('active', 'planning') ORDER BY p.name"
            ).fetchall()

            # Open tasks
            tasks = conn.execute(
                "SELECT t.title, t.priority, t.status, t.due_date, p.name as project_name "
                "FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
                "WHERE t.status != 'done' "
                "ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
                f"WHEN 'medium' THEN 2 ELSE 3 END LIMIT {TASK_DISPLAY_LIMIT}"
            ).fetchall()

            # Contacts (top 20)
            contacts = conn.execute(
                "SELECT name, company, role FROM contacts WHERE status = 'active' ORDER BY name LIMIT 20"
            ).fetchall()

        if projects:
            projects_ctx = "\n".join(
                f"- {p['name']} ({p['status']}) — {p['open_tasks']} open, {p['done_tasks']} done"
                + (f", client: {p['client']}" if p["client"] else "")
                for p in projects
            )
        else:
            projects_ctx = "No active projects."

        if tasks:
            tasks_ctx = "\n".join(
                f"- [{t['priority'] or 'medium'}] {t['title']}"
                + (f" ({t['project_name']})" if t["project_name"] else "")
                + (f" — due {t['due_date']}" if t["due_date"] else "")
                for t in tasks
            )
        else:
            tasks_ctx = "No open tasks."

        if contacts:
            contacts_ctx = "\n".join(
                f"- {c['name']}"
                + (f" — {c['company']}" if c["company"] else "")
                + (f" ({c['role']})" if c["role"] else "")
                for c in contacts
            )
        else:
            contacts_ctx = "No contacts."

        # Project names for fuzzy matching reference
        project_names = [p["name"] for p in projects]

        # New user section if no data exists yet
        new_user_section = ""
        if not projects and not contacts:
            new_user_section = """
## New User
This user just set up the bot and has no projects or contacts yet.
Be encouraging and suggest /new to create their first project.
Keep it simple — don't overwhelm with features.
"""

        return f"""You are the Telegram interface for Software of You — {owner_name}'s personal data platform.

You're running locally on {owner_name}'s machine, with direct access to all SoY data.

## {owner_name}'s Projects
{projects_ctx}

## Open Tasks
{tasks_ctx}

## Key Contacts
{contacts_ctx}

## Known Project Names (for matching)
{json.dumps(project_names)}
{new_user_section}
## Behavior
- Keep responses concise — this is Telegram on mobile.
- When the user mentions a task or TODO, capture it by including a marker line in your response:
  [TASK: title | project_name | priority]
  Example: [TASK: Review homepage layout | The Grow App | medium]
- When the user shares a note, idea, or insight, capture it:
  [NOTE: title | content | project_name]
  Example: [NOTE: API design thought | Should use REST not GraphQL for simplicity | The Grow App]
- project_name must match one of the known project names above (or be empty if unclear).
- priority must be one of: low, medium, high, urgent. Default to medium.
- You can include multiple markers in one response.
- After the markers, write your conversational response. The markers will be stripped before the user sees it.
- Never fabricate data. If you don't have information, say so.
- Be warm but efficient. Short paragraphs, not walls of text.
- FORMATTING: This is Telegram — no markdown tables, no headers. Use *bold* for emphasis, bullet points (•) for lists, and plain text. Keep it scannable on a phone screen.
- **/dev commands**: If the user asks you to do dev work, make code changes, fix bugs, build features, or anything requiring actual code edits in a project workspace — tell them to use /dev. You cannot make code changes yourself. If they want to start a brand new project, suggest /new.
  • /new <slug> <instruction> — create a new project from scratch (e.g. "/new acme-landing Build a modern landing page")
  • /delete <project> — delete a project with multi-step confirmation (Vercel, DB, workspace, optionally GitHub)
  • /dev <project> <instruction> — spawn a dev session on an existing project (e.g. "/dev grow Fix the nav bug")
  • /sessions — list recent dev sessions
  • /session <id> — view full output of a session
  • /kill <id> — kill a running session
  • /approve <id> — merge a completed session's branch into main
  • /reject <id> — discard a session's branch"""

    # ── Task/Note Capture ──

    def _parse_markers(self, text):
        """Parse [TASK:] and [NOTE:] markers from Claude's response."""
        tasks = []
        notes = []

        for match in re.finditer(r'\[TASK:\s*([^]]+)\]', text):
            parts = [p.strip() for p in match.group(1).split("|")]
            title = parts[0] if parts else None
            project = parts[1] if len(parts) > 1 and parts[1] else None
            priority = parts[2] if len(parts) > 2 and parts[2] else "medium"
            if title:
                tasks.append({"title": title, "project": project, "priority": priority})

        for match in re.finditer(r'\[NOTE:\s*([^]]+)\]', text):
            parts = [p.strip() for p in match.group(1).split("|")]
            title = parts[0] if parts else None
            content = parts[1] if len(parts) > 1 and parts[1] else None
            project = parts[2] if len(parts) > 2 and parts[2] else None
            if title:
                notes.append({"title": title, "content": content, "project": project})

        # Strip markers from visible response
        cleaned = re.sub(r'\[TASK:\s*[^]]+\]\s*\n?', '', text)
        cleaned = re.sub(r'\[NOTE:\s*[^]]+\]\s*\n?', '', cleaned)
        cleaned = cleaned.strip()

        return tasks, notes, cleaned

    def _fuzzy_match_project(self, conn, project_name):
        """Find a project by fuzzy name match. Returns (project_id, project_name) or (None, None)."""
        if not project_name:
            return None, None

        # Exact match (case-insensitive)
        row = conn.execute(
            "SELECT id, name FROM projects WHERE LOWER(name) = LOWER(?)", (project_name,)
        ).fetchone()
        if row:
            return row["id"], row["name"]

        # Partial match
        row = conn.execute(
            "SELECT id, name FROM projects WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{project_name}%",),
        ).fetchone()
        if row:
            return row["id"], row["name"]

        # Slug match — convert "test-cafe" to "test cafe" and try again
        if "-" in project_name:
            deslug = project_name.replace("-", " ")
            row = conn.execute(
                "SELECT id, name FROM projects WHERE LOWER(name) = LOWER(?)", (deslug,)
            ).fetchone()
            if row:
                return row["id"], row["name"]
            row = conn.execute(
                "SELECT id, name FROM projects WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{deslug}%",),
            ).fetchone()
            if row:
                return row["id"], row["name"]

        # Match by workspace directory name
        row = conn.execute(
            "SELECT id, name FROM projects WHERE workspace_path LIKE ?",
            (f"%/{project_name}",),
        ).fetchone()
        if row:
            return row["id"], row["name"]

        return None, None

    def _capture_items(self, tasks, notes):
        """Insert captured tasks/notes into local SoY database."""
        with self._db() as conn:
            captured = []

            for task in tasks:
                project_id, project_name = self._fuzzy_match_project(conn, task.get("project"))
                if not project_id and task.get("project"):
                    project_id, project_name = self._get_or_create_inbox(conn)

                priority = task.get("priority", "medium")
                if priority not in ("low", "medium", "high", "urgent"):
                    priority = "medium"

                conn.execute(
                    "INSERT INTO tasks (project_id, title, status, priority, created_at, updated_at) "
                    "VALUES (?, ?, 'todo', ?, datetime('now'), datetime('now'))",
                    (project_id, task["title"], priority),
                )
                local_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
                conn.execute(
                    "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                    "VALUES ('task', ?, 'created', ?, datetime('now'))",
                    (local_id, json.dumps({"source": "telegram", "title": task["title"]})),
                )
                proj_label = f" ({project_name})" if project_name else ""
                captured.append(f"Task: {task['title']}{proj_label}")

            for note in notes:
                project_id, project_name = self._fuzzy_match_project(conn, note.get("project"))
                conn.execute(
                    "INSERT INTO standalone_notes (title, content, linked_projects, created_at, updated_at) "
                    "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                    (note["title"], note.get("content"), project_name),
                )
                local_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
                conn.execute(
                    "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                    "VALUES ('standalone_note', ?, 'created', ?, datetime('now'))",
                    (local_id, json.dumps({"source": "telegram", "title": note["title"]})),
                )
                captured.append(f"Note: {note['title']}")

            conn.commit()
        return captured

    def _get_or_create_inbox(self, conn):
        """Get or create inbox project for unmatched items."""
        row = conn.execute(
            "SELECT id, name FROM projects WHERE name = ?", (INBOX_PROJECT_NAME,)
        ).fetchone()
        if row:
            return row["id"], row["name"]
        conn.execute(
            "INSERT INTO projects (name, status, description, created_at, updated_at) "
            "VALUES (?, 'active', 'Items captured via Telegram bot', datetime('now'), datetime('now'))",
            (INBOX_PROJECT_NAME,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, name FROM projects WHERE name = ?", (INBOX_PROJECT_NAME,)
        ).fetchone()
        return row["id"], row["name"]

    # ── Claude Integration ──

    def _call_claude(self, user_text, session_id):
        """Call claude -p with conversation context."""
        system_prompt = self._build_system_prompt()
        history = self._get_history(session_id)

        # Build prompt with conversation history
        prompt_parts = []
        if history:
            prompt_parts.append("## Recent conversation:")
            for msg in history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                prompt_parts.append(f"{role_label}: {msg['content']}")
            prompt_parts.append("")
        prompt_parts.append(f"User: {user_text}")

        prompt = "\n".join(prompt_parts)

        try:
            # Clean env: remove CLAUDECODE to avoid nested-session detection
            clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

            result = subprocess.run(
                [
                    "claude", "-p",
                    "--system-prompt", system_prompt,
                    "--model", DEFAULT_MODEL,
                    "--no-session-persistence",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT,
                cwd=PLUGIN_ROOT,
                env=clean_env,
            )
            self.last_claude_call = time.time()

            if result.returncode != 0:
                stderr = result.stderr.strip()
                if stderr:
                    self._log_error(f"claude -p error: {stderr}", user_msg=user_text)
                if result.stdout.strip():
                    return result.stdout.strip()
                if stderr:
                    return f"Error: {stderr[:200]}"
                return "Something went wrong."

            return result.stdout.strip() or "I processed that but had nothing to say."

        except subprocess.TimeoutExpired:
            self._log_error("claude -p timed out", user_msg=user_text)
            return "That took too long — try a simpler question or break it up."
        except FileNotFoundError:
            self._log_error("claude CLI not found in PATH", user_msg=user_text)
            return "Error: `claude` CLI not found. Make sure Claude Code is installed."
        except Exception as e:
            self._log_error(str(e), user_msg=user_text)
            return "Something went wrong processing that."

    # ── Dev Sessions ──

    def _resolve_project_for_dev(self, text):
        """Resolve a project name from /dev args.

        Supports: numeric ID, slug (hyphens), partial name, progressive prefix.
        Returns (project_id, project_name, workspace_path, instruction) or raises ValueError.
        """
        with self._db() as conn:
            projects = conn.execute(
                "SELECT id, name, workspace_path FROM projects WHERE status IN ('active', 'planning')"
            ).fetchall()

        if not projects:
            raise ValueError("No active projects found.")

        words = text.split()

        # 1. Numeric ID: /dev 8 <instruction>
        if words[0].isdigit():
            pid = int(words[0])
            matched = next((p for p in projects if p["id"] == pid), None)
            if matched:
                instruction = " ".join(words[1:]).strip()
                if not instruction:
                    raise ValueError("No instruction provided. Usage: /dev <id> <instruction>")
                return self._validate_project_workspace(matched, instruction)
            raise ValueError(f"No active project with ID {pid}.")

        # 2. Progressive prefix matching (with de-slugging)
        matched = None
        instruction_start = 0

        for i in range(1, len(words) + 1):
            prefix = " ".join(words[:i]).lower()
            deslugged = prefix.replace("-", " ")
            candidates = self._match_projects(projects, prefix, deslugged)
            if len(candidates) == 1:
                matched = candidates[0]
                instruction_start = i
            elif len(candidates) == 0:
                break

        if matched:
            instruction = " ".join(words[instruction_start:]).strip()
            if not instruction:
                raise ValueError("No instruction provided. Usage: /dev <project> <instruction>")
            return self._validate_project_workspace(matched, instruction)

        # 3. Fallback: first word only
        first = words[0].lower()
        deslugged = first.replace("-", " ")
        candidates = self._match_projects(projects, first, deslugged)
        if len(candidates) == 1:
            instruction = " ".join(words[1:]).strip()
            if not instruction:
                raise ValueError("No instruction provided. Usage: /dev <project> <instruction>")
            return self._validate_project_workspace(candidates[0], instruction)

        # 4. Ambiguous or no match — show candidates with IDs
        if len(candidates) > 1:
            listing = "\n".join(f"• `{p['id']}` — {p['name']}" for p in candidates)
            raise ValueError(
                f"Multiple matches:\n{listing}\n\n"
                "Use the project ID: `/dev <id> <instruction>`")

        listing = "\n".join(f"• `{p['id']}` — {p['name']}" for p in projects)
        raise ValueError(f"No matching project.\n\n{listing}")

    @staticmethod
    def _match_projects(projects, prefix, deslugged=None):
        """Match projects by name prefix, substring, or workspace directory name."""
        if deslugged is None:
            deslugged = prefix
        seen = set()
        result = []
        for p in projects:
            name = p["name"].lower()
            dirname = os.path.basename(p["workspace_path"] or "").lower()
            if (name.startswith(prefix) or prefix in name
                    or name.startswith(deslugged) or deslugged in name
                    or dirname == prefix or dirname == prefix.replace(" ", "-")):
                if p["id"] not in seen:
                    seen.add(p["id"])
                    result.append(p)
        return result

    @staticmethod
    def _validate_project_workspace(matched, instruction):
        """Validate workspace exists. Returns (id, name, workspace, instruction)."""
        workspace = matched["workspace_path"]
        if not workspace:
            raise ValueError(f"No workspace path set for {matched['name']}. Set one with /project first.")
        workspace = os.path.expanduser(workspace)
        if not os.path.isdir(workspace):
            raise ValueError(f"Workspace not found: {workspace}")
        return matched["id"], matched["name"], workspace, instruction

    @staticmethod
    def _get_vercel_production_url(workspace):
        """Get the actual Vercel production URL by querying the latest deployment."""
        try:
            # Get latest deployment URL
            ls_result = subprocess.run(
                ["vercel", "ls", "--format", "json"],
                capture_output=True, text=True, cwd=workspace, timeout=15,
            )
            if ls_result.returncode != 0:
                return None
            ls_data = json.loads(ls_result.stdout)
            deployments = ls_data.get("deployments", ls_data) if isinstance(ls_data, dict) else ls_data
            if not deployments:
                return None
            latest_url = deployments[0].get("url")
            if not latest_url:
                return None

            # Inspect latest deployment to get production aliases
            inspect_result = subprocess.run(
                ["vercel", "inspect", latest_url, "--format", "json"],
                capture_output=True, text=True, cwd=workspace, timeout=15,
            )
            if inspect_result.returncode == 0:
                inspect_data = json.loads(inspect_result.stdout)
                aliases = inspect_data.get("aliases", [])
                # Pick the shortest .vercel.app alias (the canonical one)
                vercel_aliases = [a for a in aliases if a.endswith(".vercel.app")]
                if vercel_aliases:
                    best = min(vercel_aliases, key=len)
                    return f"https://{best}"

            # Fallback: construct from projectName in .vercel/project.json
            config_path = os.path.join(workspace, ".vercel", "project.json")
            with open(config_path) as f:
                config = json.load(f)
            project_name = config.get("projectName")
            if project_name:
                return f"https://{project_name}.vercel.app"
        except Exception:
            pass
        return None

    @staticmethod
    def _get_github_url(workspace):
        """Extract GitHub owner/repo URL from git remote. Returns URL or None."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=workspace, timeout=5,
            )
            remote = result.stdout.strip()
            if not remote:
                return None
            # SSH: git@github.com:owner/repo.git → https://github.com/owner/repo
            match = re.match(r'git@github\.com:(.+?)(?:\.git)?$', remote)
            if match:
                return f"https://github.com/{match.group(1)}"
            # HTTPS: https://github.com/owner/repo.git → https://github.com/owner/repo
            match = re.match(r'https://github\.com/(.+?)(?:\.git)?$', remote)
            if match:
                return f"https://github.com/{match.group(1)}"
            return None
        except Exception:
            return None

    def _scaffold_project(self, slug, display_name, workspace):
        """Create minimal project files in the workspace."""
        gitignore = "node_modules/\n.vercel/\n.env\n.DS_Store\n"
        with open(os.path.join(workspace, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(gitignore)

        index_html = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            f"  <title>{display_name}</title>\n"
            "</head>\n<body>\n"
            f"  <h1>{display_name}</h1>\n"
            "</body>\n</html>\n"
        )
        with open(os.path.join(workspace, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)

        package_json = json.dumps(
            {"name": slug, "version": "0.0.1", "private": True},
            indent=2,
        ) + "\n"
        with open(os.path.join(workspace, "package.json"), "w", encoding="utf-8") as f:
            f.write(package_json)

        claude_md = (
            f"# {display_name}\n\n"
            "IMPORTANT: Never push to main without explicit instruction. "
            "Commit on your branch only.\n"
        )
        with open(os.path.join(workspace, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(claude_md)

    def _cleanup_failed_project(self, project_id):
        """Remove DB records for a project that failed during /new creation.
        Leaves the workspace directory for inspection."""
        with self._db() as conn:
            conn.execute("DELETE FROM activity_log WHERE entity_type = 'project' AND entity_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    def _handle_pending_confirmation(self, text, chat_id):
        """Route pending confirmation responses."""
        conf = self.pending_confirmations.pop(chat_id)
        action = conf["action"]

        if text.strip().lower() == "cancel":
            self.send_message(chat_id, "Cancelled.")
            return

        if action == "delete_project":
            if text.strip().lower() == conf["project_name"].lower():
                self._execute_project_deletion(chat_id, conf)
            else:
                self.send_message(chat_id,
                    f"❌ Name didn't match. Expected *{conf['project_name']}*. Deletion cancelled.")

        elif action == "delete_repo":
            if text.strip().lower() == "delete repo":
                self._execute_repo_deletion(chat_id, conf)
            else:
                # Keep repo → keep project in DB, clear workspace path
                project_id = conf.get("project_id")
                project_name = conf.get("project_name", "Project")
                if project_id:
                    with self._db() as conn:
                        conn.execute(
                            "UPDATE projects SET workspace_path = NULL, updated_at = datetime('now') "
                            "WHERE id = ?", (project_id,))
                        conn.commit()
                self.send_message(chat_id,
                    f"GitHub repo kept. *{project_name}* stays in SoY (workspace cleared).")

        elif action == "dirty_workspace":
            choice = text.strip().lower()
            workspace = conf["workspace"]
            if choice == "commit":
                result = subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True, cwd=workspace, timeout=10,
                )
                result = subprocess.run(
                    ["git", "commit", "-m", "WIP: commit uncommitted changes via Telegram"],
                    capture_output=True, text=True, cwd=workspace, timeout=10,
                )
                if result.returncode != 0:
                    self.send_message(chat_id, f"❌ Commit failed: {result.stderr.strip()[:300]}")
                    return
                self.send_message(chat_id, "✅ Changes committed.")
            elif choice == "stash":
                result = subprocess.run(
                    ["git", "stash", "push", "-m", "soy-bot: stashed before dev session"],
                    capture_output=True, text=True, cwd=workspace, timeout=10,
                )
                if result.returncode != 0:
                    self.send_message(chat_id, f"❌ Stash failed: {result.stderr.strip()[:300]}")
                    return
                self.send_message(chat_id, "📦 Changes stashed.")
            else:
                self.send_message(chat_id, "Cancelled.")
                return
            # Proceed with dev session
            self._launch_dev_session(
                conf["project_id"], conf["project_name"], workspace,
                conf["instruction"], chat_id, conf["model"])

    def _handle_delete_project(self, args, chat_id):
        """Handle /delete — delete a project with multi-step confirmation."""
        if not args:
            self.send_message(chat_id,
                "*Usage:* /delete <project>\n\n"
                "Example: /delete test-cafe\n"
                "Example: /delete 7")
            return

        with self._db() as conn:
            # Resolve by numeric ID or fuzzy name
            project_id = None
            project_name = None
            workspace = None

            if args.isdigit():
                row = conn.execute(
                    "SELECT id, name, workspace_path FROM projects WHERE id = ?",
                    (int(args),),
                ).fetchone()
                if row:
                    project_id, project_name, workspace = row["id"], row["name"], row["workspace_path"]
            else:
                project_id, project_name = self._fuzzy_match_project(conn, args)
                if project_id:
                    row = conn.execute(
                        "SELECT workspace_path FROM projects WHERE id = ?", (project_id,)
                    ).fetchone()
                    workspace = row["workspace_path"] if row else None

            if not project_id:
                all_projects = conn.execute(
                    "SELECT name, workspace_path FROM projects "
                    "WHERE status IN ('active', 'planning') ORDER BY name"
                ).fetchall()
                suggestions = []
                search = args.lower().replace("-", " ")
                for p in all_projects:
                    name_lower = p["name"].lower()
                    slug = os.path.basename(p["workspace_path"] or "") if p["workspace_path"] else ""
                    if any(w in name_lower or w in slug for w in search.split()):
                        suggestions.append(p["name"])
                msg = f"❌ Project not found: {args}"
                if suggestions:
                    msg += "\n\nDid you mean?\n" + "\n".join(f"• {s}" for s in suggestions[:5])
                else:
                    names = [p["name"] for p in all_projects[:10]]
                    if names:
                        msg += "\n\nActive projects:\n" + "\n".join(f"• {n}" for n in names)
                self.send_message(chat_id, msg)
                return

            # Block if active dev sessions or deploys on this project
            active_sessions = [
                sid for sid, s in self.active_dev_sessions.items()
                if s.get("project_id") == project_id
            ]
            active_deploy_sessions = [
                sid for sid, d in self.active_deploys.items()
                if d.get("project_id") == project_id
            ]
            if active_sessions or active_deploy_sessions:
                ids = ", ".join(active_sessions + active_deploy_sessions)
                self.send_message(chat_id,
                    f"❌ Can't delete — active sessions: {ids}\n"
                    "Use /kill to stop them first.")
                return

            # Gather stats
            task_count = conn.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE project_id = ?", (project_id,)
            ).fetchone()["c"]
            session_count = conn.execute(
                "SELECT COUNT(*) as c FROM telegram_dev_sessions WHERE project_id = ?", (project_id,)
            ).fetchone()["c"]
            preview_urls = conn.execute(
                "SELECT preview_url FROM telegram_dev_sessions "
                "WHERE project_id = ? AND preview_url IS NOT NULL",
                (project_id,),
            ).fetchall()

        # Gather live URLs
        github_url = self._get_github_url(workspace) if workspace and os.path.isdir(workspace) else None
        vercel_url = self._get_vercel_production_url(workspace) if workspace and os.path.isdir(workspace) else None

        # Build summary
        lines = [f"🗑 *Delete: {project_name}*\n"]
        if workspace:
            lines.append(f"Workspace: `{workspace}`")
        if github_url:
            lines.append(f"GitHub: {github_url}")
        if vercel_url:
            lines.append(f"Vercel: {vercel_url}")
        lines.append(f"Tasks: {task_count}")
        lines.append(f"Dev sessions: {session_count}")
        if preview_urls:
            lines.append(f"Preview URLs: {len(preview_urls)}")

        lines.append(f"\n*This will delete:*")
        lines.append("• Vercel deployment (if exists)")
        lines.append("• Workspace directory")
        if github_url:
            lines.append("• GitHub repo + DB records prompted separately")
        else:
            lines.append("• All DB records (tasks, sessions, activity)")

        lines.append(f"\nType *{project_name}* to confirm, or *cancel* to abort.")
        self.send_message(chat_id, "\n".join(lines))

        # Store pending confirmation
        self.pending_confirmations[chat_id] = {
            "action": "delete_project",
            "project_id": project_id,
            "project_name": project_name,
            "workspace": workspace,
            "github_url": github_url,
            "expires_at": time.time() + CONFIRMATION_TIMEOUT,
        }

    def _execute_project_deletion(self, chat_id, data):
        """Delete Vercel deployment and workspace. DB deletion depends on GitHub outcome."""
        project_id = data["project_id"]
        project_name = data["project_name"]
        workspace = data["workspace"]
        github_url = data["github_url"]

        self.send_message(chat_id, f"🗑 Deleting *{project_name}*...")

        errors = []

        # 1. Remove Vercel project
        if workspace and os.path.isdir(workspace):
            vercel_config = os.path.join(workspace, ".vercel", "project.json")
            if os.path.exists(vercel_config):
                try:
                    with open(vercel_config) as f:
                        config = json.load(f)
                    vercel_name = config.get("projectName")
                    if vercel_name:
                        result = subprocess.run(
                            ["vercel", "rm", vercel_name, "--yes"],
                            capture_output=True, text=True,
                            cwd=workspace, timeout=60,
                        )
                        if result.returncode != 0:
                            errors.append(f"Vercel removal warning: {result.stderr.strip()[:200]}")
                except Exception as e:
                    errors.append(f"Vercel removal warning: {e}")

        # 2. Remove workspace directory
        if workspace and os.path.isdir(workspace):
            try:
                shutil.rmtree(workspace)
            except Exception as e:
                errors.append(f"Workspace removal error: {e}")

        # 3. If no GitHub repo, delete DB records now (fully cleaned up)
        if not github_url:
            self._delete_project_db_records(project_id)
            lines = [f"✅ *{project_name}* deleted."]
            if errors:
                lines.append("\n⚠️ Warnings:")
                lines.extend(f"• {e}" for e in errors)
            self.send_message(chat_id, "\n".join(lines))
            return

        # 4. GitHub repo exists — prompt before deleting DB
        lines = [f"✅ Vercel + workspace removed for *{project_name}*."]
        if errors:
            lines.append("\n⚠️ Warnings:")
            lines.extend(f"• {e}" for e in errors)

        match = re.match(r'https://github\.com/(.+)$', github_url)
        repo_name = match.group(1) if match else None
        if repo_name:
            lines.append(f"\nGitHub repo still exists: {github_url}")
            lines.append("Type *delete repo* to remove it and the project record.")
            lines.append("Anything else keeps the repo and the project in SoY.")
            self.pending_confirmations[chat_id] = {
                "action": "delete_repo",
                "github_url": github_url,
                "repo_name": repo_name,
                "project_id": project_id,
                "project_name": project_name,
                "expires_at": time.time() + CONFIRMATION_TIMEOUT,
            }

        self.send_message(chat_id, "\n".join(lines))

    def _delete_project_db_records(self, project_id):
        """Remove all DB records for a project."""
        with self._db() as conn:
            conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM telegram_dev_sessions WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM activity_log WHERE entity_type = 'project' AND entity_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    def _execute_repo_deletion(self, chat_id, data):
        """Delete a GitHub repo and project DB records after confirmation."""
        repo_name = data["repo_name"]
        github_url = data["github_url"]
        project_id = data["project_id"]
        project_name = data["project_name"]

        try:
            result = subprocess.run(
                ["gh", "repo", "delete", repo_name, "--yes"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                self._delete_project_db_records(project_id)
                self.send_message(chat_id, f"✅ GitHub repo deleted and *{project_name}* removed from SoY.")
            else:
                self.send_message(chat_id,
                    f"❌ Failed to delete repo: {result.stderr.strip()[:300]}")
        except Exception as e:
            self.send_message(chat_id, f"❌ Error deleting repo: {e}")

    def _handle_new_project(self, args, chat_id):
        """Handle /new — create a project from scratch and start a dev session."""
        model, args = self._extract_model_flag(args)

        if model not in ALLOWED_MODELS:
            self.send_message(chat_id,
                f"❌ Unknown model: {model}. Use: {', '.join(sorted(ALLOWED_MODELS))}")
            return

        # Parse: first word = slug, rest = instruction
        parts = args.split(None, 1)
        if not parts or len(parts) < 2:
            self.send_message(chat_id,
                "*Usage:* /new <slug> <instruction>\n\n"
                "Example: /new acme-landing Build a modern landing page\n\n"
                f"Options: --model opus (default: {DEFAULT_MODEL})")
            return

        slug = parts[0].lower()
        instruction = parts[1].strip()

        # Validate slug format
        if not re.match(r'^[a-z][a-z0-9-]*$', slug):
            self.send_message(chat_id,
                "❌ Slug must start with a letter and contain only lowercase letters, numbers, and hyphens.")
            return

        # Auto-prettify display name
        display_name = slug.replace("-", " ").title()
        workspace = os.path.expanduser(f"{WORKSPACE_BASE}/{slug}")

        # Check for duplicate directory
        if os.path.exists(workspace):
            self.send_message(chat_id, f"❌ Directory already exists: `{workspace}`")
            return

        # Check for duplicate project name in DB
        with self._db() as conn:
            existing = conn.execute(
                "SELECT id FROM projects WHERE LOWER(name) = LOWER(?)", (display_name,)
            ).fetchone()
        if existing:
            self.send_message(chat_id, f"❌ Project '{display_name}' already exists.")
            return

        # Check concurrent session limit
        active_count = len(self.active_dev_sessions)
        if active_count >= DEV_SESSION_MAX_ACTIVE:
            self.send_message(chat_id,
                f"❌ Max {DEV_SESSION_MAX_ACTIVE} concurrent sessions. "
                f"Wait for one to finish or /kill one.")
            return

        # Check gh CLI
        if not shutil.which("gh"):
            self.send_message(chat_id, "❌ `gh` CLI not found. Install it: https://cli.github.com")
            return

        # Warn about optional vercel CLI (non-blocking)
        if not shutil.which("vercel"):
            self.send_message(chat_id,
                "⚠️ `vercel` CLI not found — preview deploys will be skipped.\n"
                "Install it: `npm i -g vercel`")

        self.send_message(chat_id,
            f"⚙️ Creating *{display_name}*...\n"
            f"Workspace: `{workspace}`")

        project_id = None
        try:
            # Insert project into DB
            with self._db() as conn:
                cursor = conn.execute(
                    "INSERT INTO projects (name, status, workspace_path, created_at, updated_at) "
                    "VALUES (?, 'active', ?, datetime('now'), datetime('now'))",
                    (display_name, workspace),
                )
                project_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) "
                    "VALUES ('project', ?, 'created', ?, datetime('now'))",
                    (project_id, f"Created via /new from Telegram"),
                )
                conn.commit()

            # Create workspace and scaffold files
            os.makedirs(workspace, exist_ok=True)
            self._scaffold_project(slug, display_name, workspace)

            # Git init + initial commit
            subprocess.run(
                ["git", "init"], capture_output=True, text=True,
                cwd=workspace, timeout=10, check=True,
            )
            subprocess.run(
                ["git", "branch", "-M", "main"], capture_output=True, text=True,
                cwd=workspace, timeout=5, check=True,
            )
            subprocess.run(
                ["git", "add", "-A"], capture_output=True, text=True,
                cwd=workspace, timeout=10, check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], capture_output=True, text=True,
                cwd=workspace, timeout=10, check=True,
            )

            # Create GitHub repo
            if not self._ensure_git_remote(workspace, display_name, chat_id):
                raise ValueError("Failed to create GitHub remote.")

            # Spawn dev session (longer timeout for greenfield builds)
            session_id, branch_name = self._spawn_dev_session(
                project_id, display_name, workspace, instruction, chat_id, model,
                timeout=NEW_PROJECT_TIMEOUT,
            )

            self.send_message(chat_id,
                f"🚀 *{display_name}* is live!\n\n"
                f"*Project ID:* {project_id}\n"
                f"*Session:* `{session_id}`\n"
                f"*Branch:* `{branch_name}`\n"
                f"*Model:* {model}\n"
                f"*Instruction:* {instruction}\n\n"
                "I'll message you when the session completes with a preview link.")

        except Exception as e:
            if project_id:
                self._cleanup_failed_project(project_id)
            self.send_message(chat_id, f"❌ Failed to create project: {e}")

    def _ensure_vercel_git_connected(self, workspace, chat_id):
        """Ensure the Vercel project is connected to its GitHub repo for auto-deploys.
        Non-blocking — logs a hint if it can't connect, but doesn't fail the session."""
        github_url = self._get_github_url(workspace)
        if not github_url:
            return  # No GitHub remote to connect

        # Check if .vercel/project.json exists (Vercel is linked)
        vercel_config = os.path.join(workspace, ".vercel", "project.json")
        if not os.path.exists(vercel_config):
            return  # Vercel not linked — preview deploys handle this

        try:
            result = subprocess.run(
                ["vercel", "git", "connect", github_url],
                input="y\n", capture_output=True, text=True,
                cwd=workspace, timeout=15,
            )
            output = result.stdout + result.stderr
            if "Connected" in output or "already connected" in output:
                return  # Success (or already connected)
            # Connection failed — guide user
            self.send_message(chat_id,
                f"⚠️ Couldn't auto-connect Vercel to GitHub.\n"
                f"To enable auto-deploy on push, run:\n"
                f"`cd {workspace} && vercel git connect`")
        except FileNotFoundError:
            pass  # vercel CLI not installed — preview deploys won't work either
        except Exception:
            pass

    def _ensure_git_remote(self, workspace, project_name, chat_id):
        """Check workspace has git + remote. Auto-creates GitHub repo if missing.
        Returns True if ready, False if blocked."""
        # Check if git repo exists
        git_dir = os.path.join(workspace, ".git")
        if not os.path.isdir(git_dir):
            self.send_message(chat_id,
                f"❌ No git repo in workspace.\n\n"
                f"Initialize one first:\n"
                f"`cd {workspace} && git init && git add -A && git commit -m 'Initial commit'`")
            return False

        # Check if remote exists
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=workspace, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Remote exists — ensure Vercel is connected to it
            self._ensure_vercel_git_connected(workspace, chat_id)
            return True

        # No remote — try to create GitHub repo
        self.send_message(chat_id,
            f"⚙️ No GitHub remote found for {project_name}. Creating one...")

        # Sanitize project name for repo name
        repo_name = re.sub(r'[^a-zA-Z0-9-]', '-', project_name).strip('-').lower()

        try:
            gh_result = subprocess.run(
                ["gh", "repo", "create", repo_name, "--private", "--source=.", "--push"],
                capture_output=True, text=True, cwd=workspace, timeout=30,
            )
            if gh_result.returncode == 0:
                self.send_message(chat_id, f"✅ Created private repo: `{repo_name}`")
                # Connect Vercel to the new repo
                self._ensure_vercel_git_connected(workspace, chat_id)
                return True
            else:
                error = gh_result.stderr.strip() or gh_result.stdout.strip()
                self.send_message(chat_id,
                    f"❌ Couldn't create GitHub repo.\n\n"
                    f"```\n{error[:300]}\n```\n\n"
                    f"Add a remote manually:\n"
                    f"`cd {workspace} && gh repo create {repo_name} --private --source=. --push`")
                return False
        except FileNotFoundError:
            self.send_message(chat_id,
                f"❌ `gh` CLI not found. Add a remote manually:\n"
                f"`cd {workspace} && git remote add origin git@github.com:YOUR_USER/{repo_name}.git`")
            return False

    def _launch_dev_session(self, project_id, project_name, workspace, instruction, chat_id, model=DEFAULT_MODEL, timeout=None):
        """Validate, spawn, and notify for a dev session. Used by /dev and confirmation handlers."""
        try:
            session_id, branch_name = self._spawn_dev_session(
                project_id, project_name, workspace, instruction, chat_id, model, timeout)
        except ValueError as e:
            self.send_message(chat_id, f"❌ {e}")
            return
        self.send_message(chat_id,
            f"🔧 *Dev session started* (`{session_id}`)\n\n"
            f"*Project:* {project_name}\n"
            f"*Branch:* `{branch_name}`\n"
            f"*Model:* {model}\n"
            f"*Instruction:* {instruction}\n\n"
            "I'll message you when it's done. "
            "A preview deploy will follow automatically.")

    def _spawn_dev_session(self, project_id, project_name, workspace, instruction, chat_id, model=DEFAULT_MODEL, timeout=None):
        """Spawn a background claude -p session for dev work on an isolated branch."""
        session_id = uuid.uuid4().hex[:8]
        branch_name = f"{DEV_BRANCH_PREFIX}{session_id}"

        # Block concurrent operations on the same workspace
        if workspace in self.workspace_locks:
            raise ValueError(
                "This workspace is busy (dev session or approve/reject in progress). "
                "Wait for it to finish or /kill the session first."
            )
        self.workspace_locks.add(workspace)

        # Workspace must be clean before branching — caller handles dirty state
        try:
            porcelain = subprocess.run(
                ["git", "status", "--porcelain", "-uno"],
                capture_output=True, text=True, cwd=workspace, timeout=5,
            )
            if porcelain.stdout.strip():
                raise ValueError("Workspace has uncommitted changes.")

            subprocess.run(
                ["git", "checkout", "main"],
                capture_output=True, text=True, cwd=workspace, timeout=10,
                check=True,
            )
            # Best-effort pull
            subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True, text=True, cwd=workspace, timeout=15,
            )
            # Capture HEAD sha
            git_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=workspace, timeout=5,
            ).stdout.strip()
            # Create dev branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True, text=True, cwd=workspace, timeout=10,
                check=True,
            )
        except ValueError:
            self.workspace_locks.discard(workspace)
            raise
        except subprocess.CalledProcessError as e:
            self.workspace_locks.discard(workspace)
            raise ValueError(f"Git setup failed: {e.stderr.strip() or e}")
        except Exception as e:
            self.workspace_locks.discard(workspace)
            raise ValueError(f"Git setup failed: {e}")

        # Create temp file for stdout (owner-only permissions)
        stdout_file = tempfile.NamedTemporaryFile(
            prefix=f"soy_dev_{session_id}_", suffix=".log",
            delete=False, mode="w",
        )
        os.chmod(stdout_file.name, stat.S_IRUSR | stat.S_IWUSR)

        # Fetch previous session context for this project
        prev_context = ""
        with self._db() as conn:
            prev = conn.execute(
                "SELECT instruction, status, output_summary FROM telegram_dev_sessions "
                "WHERE project_name = ? AND status IN ('completed', 'failed') "
                "ORDER BY started_at DESC LIMIT 1",
                (project_name,),
            ).fetchone()
        if prev and prev["output_summary"]:
            prev_context = (
                f"\n\n## Previous session context\n"
                f"Instruction: {prev['instruction']}\n"
                f"Status: {prev['status']}\n"
                f"Output:\n{prev['output_summary'][:1500]}"
            )

        dev_instructions = (
            "You are running autonomously as a remote dev session triggered from Telegram. "
            f"You are on branch `{branch_name}`. "
            "Work independently — no interactive questions. Make the requested changes, "
            "commit your work with a clear commit message, and end your output with a "
            "'## Summary' section describing what you did and any issues encountered. "
            "IMPORTANT: Never push to main. Never merge to main. Commit on this branch only. "
            "The user reviews and approves merges separately via /approve."
            + prev_context
        )

        clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        # --dangerously-skip-permissions is required because dev sessions run
        # autonomously in the background with no interactive terminal to approve
        # tool calls. This is safe here because:
        #   1. Owner-only gate: only TELEGRAM_OWNER_ID can trigger sessions
        #   2. Isolated branches: all work happens on dev/<slug>-<uuid> branches
        #   3. Workspace locks: only one session per workspace at a time
        #   4. Timeouts: DEV_SESSION_TIMEOUT / NEW_PROJECT_TIMEOUT kill runaways
        #   5. Concurrent limit: max DEV_SESSION_MAX_ACTIVE sessions
        #   6. CLAUDE.md guardrails: project-level instructions constrain behavior
        #   7. Review gate: changes require explicit /approve before merging to main
        process = subprocess.Popen(
            [
                "claude", "-p",
                "--model", model,
                "--no-session-persistence",
                "--dangerously-skip-permissions",
                "--append-system-prompt", dev_instructions,
                instruction,
            ],
            stdout=stdout_file,
            stderr=subprocess.STDOUT,
            cwd=workspace,
            env=clean_env,
        )

        # Record in DB
        with self._db() as conn:
            conn.execute(
                "INSERT INTO telegram_dev_sessions "
                "(session_id, project_id, project_name, workspace_path, instruction, "
                "status, model, pid, stdout_path, git_before_sha, telegram_chat_id, "
                "branch_name, review_status) "
                "VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, 'pending')",
                (session_id, project_id, project_name, workspace, instruction,
                 model, process.pid, stdout_file.name, git_sha, str(chat_id),
                 branch_name),
            )
            conn.commit()

        # Track in memory
        self.active_dev_sessions[session_id] = {
            "process": process,
            "stdout_file": stdout_file,
            "started_at": time.time(),
            "chat_id": chat_id,
            "workspace": workspace,
            "project_name": project_name,
            "git_before_sha": git_sha,
            "branch_name": branch_name,
            "timeout": timeout or DEV_SESSION_TIMEOUT,
        }

        return session_id, branch_name

    def _check_dev_sessions(self):
        """Poll active dev sessions for completion. Non-blocking."""
        finished = []
        for sid, info in self.active_dev_sessions.items():
            proc = info["process"]
            elapsed = time.time() - info["started_at"]

            ret = proc.poll()
            if ret is not None:
                # Process finished
                finished.append((sid, ret, elapsed))
            elif elapsed > info.get("timeout", DEV_SESSION_TIMEOUT):
                # Timeout — kill it
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
                finished.append((sid, "timeout", elapsed))

        for sid, result, elapsed in finished:
            self._finalize_dev_session(sid, result, elapsed)

    def _finalize_dev_session(self, session_id, exit_result, elapsed):
        """Finalize a completed/timed-out dev session."""
        info = self.active_dev_sessions.pop(session_id, None)
        if not info:
            return

        # Release workspace lock
        self.workspace_locks.discard(info.get("workspace"))

        # Close the stdout file handle
        try:
            info["stdout_file"].close()
        except Exception:
            pass

        stdout_path = info["stdout_file"].name
        chat_id = info["chat_id"]
        workspace = info["workspace"]
        duration = int(elapsed)
        branch_name = info.get("branch_name")

        # Determine status
        if exit_result == "timeout":
            status = "timeout"
            exit_code = -1
        elif exit_result == 0:
            status = "completed"
            exit_code = 0
        else:
            status = "failed"
            exit_code = exit_result if isinstance(exit_result, int) else -1

        # Read output
        output_text = ""
        try:
            with open(stdout_path, "r") as f:
                output_text = f.read()
        except Exception:
            pass

        # Extract summary section
        summary = None
        summary_match = re.search(r'## Summary\s*\n(.*)', output_text, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()[:2000]
        elif output_text:
            # Take last 500 chars as fallback
            summary = output_text[-500:].strip()

        # Get git diff stat
        diff_stat = None
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--stat", info["git_before_sha"] or "HEAD~1", "HEAD"],
                capture_output=True, text=True, cwd=workspace, timeout=10,
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                diff_stat = diff_result.stdout.strip()
        except Exception:
            pass

        # Update DB
        with self._db() as conn:
            conn.execute(
                "UPDATE telegram_dev_sessions SET "
                "status = ?, exit_code = ?, output_summary = ?, git_diff_stat = ?, "
                "completed_at = datetime('now'), duration_seconds = ? "
                "WHERE session_id = ?",
                (status, exit_code, summary, diff_stat, duration, session_id),
            )
            conn.commit()

        # Notify user via Telegram
        status_icon = STATUS_ICONS.get(status, "❓")
        duration_str = self._format_duration(duration)

        msg = f"{status_icon} *Dev session `{session_id}`* — {status}\n"
        msg += f"*Project:* {info['project_name']}\n"
        msg += f"*Duration:* {duration_str}\n"
        if branch_name:
            msg += f"*Branch:* `{branch_name}`\n"

        if diff_stat:
            msg += f"\n```\n{diff_stat}\n```\n"

        if summary:
            # Truncate for Telegram
            if len(summary) > 1500:
                summary = summary[:1500] + "..."
            msg += f"\n{summary}"
        elif status == "timeout":
            msg += "\nSession timed out after 10 minutes."

        # Push dev branch and get commit link for completed sessions
        commit_url = None
        if status == "completed" and branch_name:
            # Push the branch so commits are visible on GitHub
            try:
                push_result = subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    capture_output=True, text=True, cwd=workspace, timeout=30,
                )
                if push_result.returncode == 0:
                    # Get HEAD commit SHA
                    sha_result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True, text=True, cwd=workspace, timeout=5,
                    )
                    sha = sha_result.stdout.strip()
                    github_url = self._get_github_url(workspace)
                    if github_url and sha:
                        commit_url = f"{github_url}/commit/{sha}"
            except Exception:
                pass  # Push failed — still continue with deploy

        # Trigger preview deploy for completed sessions with a branch
        if status == "completed" and branch_name:
            msg += "\n\n🚀 Deploying preview..."
            if commit_url:
                msg += f"\n📝 [Review code]({commit_url})"
            # No buttons here — they'll appear on the deploy result message
            self.send_message(chat_id, msg)
            self._start_preview_deploy(session_id, workspace, chat_id, info["project_name"])
        else:
            msg += f"\n\nUse /session {session_id} for full output."
            if branch_name:
                # No deploy happening, so show buttons here
                self.send_message_with_buttons(
                    chat_id, msg, self._approve_reject_buttons(session_id))
            else:
                self.send_message(chat_id, msg)

    # ── Preview Deploys ──

    def _start_preview_deploy(self, session_id, workspace, chat_id, project_name):
        """Spawn `vercel deploy --yes` in background for a completed session."""
        stdout_file = tempfile.NamedTemporaryFile(
            prefix=f"soy_deploy_{session_id}_", suffix=".log",
            delete=False, mode="w",
        )
        os.chmod(stdout_file.name, stat.S_IRUSR | stat.S_IWUSR)
        try:
            process = subprocess.Popen(
                ["vercel", "deploy", "--yes"],
                stdout=stdout_file,
                stderr=subprocess.STDOUT,
                cwd=workspace,
            )
        except FileNotFoundError:
            stdout_file.close()
            os.unlink(stdout_file.name)
            self.send_message(chat_id, "⚠️ `vercel` CLI not found — skipping preview deploy.")
            return
        except Exception as e:
            stdout_file.close()
            os.unlink(stdout_file.name)
            self.send_message(chat_id, f"⚠️ Deploy failed to start: {e}")
            return

        # Update DB
        with self._db() as conn:
            conn.execute(
                "UPDATE telegram_dev_sessions SET deploy_status = 'deploying', "
                "deploy_pid = ?, deploy_stdout_path = ? WHERE session_id = ?",
                (process.pid, stdout_file.name, session_id),
            )
            conn.commit()

        self.active_deploys[session_id] = {
            "process": process,
            "stdout_file": stdout_file,
            "started_at": time.time(),
            "chat_id": chat_id,
            "workspace": workspace,
            "project_name": project_name,
        }

    def _check_deploys(self):
        """Poll active deploys for completion. Non-blocking."""
        finished = []
        for sid, info in self.active_deploys.items():
            proc = info["process"]
            elapsed = time.time() - info["started_at"]

            ret = proc.poll()
            if ret is not None:
                finished.append((sid, ret, elapsed))
            elif elapsed > DEPLOY_TIMEOUT:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
                finished.append((sid, "timeout", elapsed))

        for sid, result, elapsed in finished:
            self._finalize_deploy(sid, result, elapsed)

    def _finalize_deploy(self, session_id, exit_result, elapsed):
        """Finalize a completed/timed-out deploy."""
        info = self.active_deploys.pop(session_id, None)
        if not info:
            return

        try:
            info["stdout_file"].close()
        except Exception:
            pass

        stdout_path = info["stdout_file"].name
        chat_id = info["chat_id"]

        # Read output and parse preview URL
        output_text = ""
        try:
            with open(stdout_path, "r") as f:
                output_text = f.read()
        except Exception:
            pass

        preview_url = None
        # Parse "Preview: <url>" line from vercel CLI output
        url_match = re.search(r'Preview:\s+(https://\S+\.vercel\.app)', output_text)
        if url_match:
            preview_url = url_match.group(1)
        else:
            # Fallback: any .vercel.app URL followed by whitespace
            url_match = re.search(r'(https://\S+\.vercel\.app)\s', output_text)
            if url_match:
                preview_url = url_match.group(1)

        if exit_result == "timeout":
            deploy_status = "deploy_failed"
        elif exit_result == 0 and preview_url:
            deploy_status = "deployed"
        else:
            deploy_status = "deploy_failed"

        # Update DB
        with self._db() as conn:
            conn.execute(
                "UPDATE telegram_dev_sessions SET deploy_status = ?, preview_url = ?, "
                "deploy_pid = NULL WHERE session_id = ?",
                (deploy_status, preview_url, session_id),
            )
            conn.commit()

        # Connect Vercel to GitHub after first successful deploy (creates .vercel/)
        if deploy_status == "deployed":
            self._ensure_vercel_git_connected(info["workspace"], chat_id)

        # Notify
        buttons = self._approve_reject_buttons(session_id)
        if deploy_status == "deployed":
            self.send_message_with_buttons(chat_id,
                f"🌐 *Preview ready* (`{session_id}`)\n\n"
                f"{preview_url}",
                buttons)
        elif exit_result == "timeout":
            self.send_message_with_buttons(chat_id,
                f"⚠️ Deploy timed out for `{session_id}` (>{DEPLOY_TIMEOUT}s).",
                buttons)
        else:
            error_preview = output_text[-500:].strip() if output_text else "No output"
            self.send_message_with_buttons(chat_id,
                f"⚠️ Deploy failed for `{session_id}`\n\n"
                f"```\n{error_preview}\n```",
                buttons)

    @staticmethod
    def _is_process_named(pid, name):
        """Check if a PID belongs to a process matching name (guards against PID reuse)."""
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True, text=True, timeout=5,
            )
            return name in result.stdout.lower()
        except Exception:
            return False

    def _recover_orphaned_sessions(self):
        """On startup, find stale 'running' sessions and deploying sessions, and clean up."""
        with self._db() as conn:
            stale = conn.execute(
                "SELECT session_id, pid, telegram_chat_id, project_name "
                "FROM telegram_dev_sessions WHERE status = 'running'"
            ).fetchall()

            for row in stale:
                pid = row["pid"]
                if pid and self._is_process_named(pid, "claude"):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass

                conn.execute(
                    "UPDATE telegram_dev_sessions SET status = 'killed', "
                    "completed_at = datetime('now') WHERE session_id = ?",
                    (row["session_id"],),
                )

                if row["telegram_chat_id"]:
                    self.send_message(
                        row["telegram_chat_id"],
                        f"⚠️ Dev session `{row['session_id']}` ({row['project_name']}) "
                        "was orphaned from a previous bot run and has been killed.",
                    )

            # Also kill stale deploys
            stale_deploys = conn.execute(
                "SELECT session_id, deploy_pid, telegram_chat_id, project_name "
                "FROM telegram_dev_sessions WHERE deploy_status = 'deploying'"
            ).fetchall()

            for row in stale_deploys:
                pid = row["deploy_pid"]
                if pid and self._is_process_named(pid, "vercel"):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass

                conn.execute(
                    "UPDATE telegram_dev_sessions SET deploy_status = 'deploy_failed', "
                    "deploy_pid = NULL WHERE session_id = ?",
                    (row["session_id"],),
                )

                if row["telegram_chat_id"]:
                    self.send_message(
                        row["telegram_chat_id"],
                        f"⚠️ Deploy for `{row['session_id']}` ({row['project_name']}) "
                        "was orphaned and has been cancelled.",
                    )

            if stale or stale_deploys:
                conn.commit()

    def _cleanup_old_temp_files(self):
        """Remove dev session and deploy temp files older than TEMP_FILE_MAX_AGE."""
        try:
            tmp_dir = tempfile.gettempdir()
            cutoff = time.time() - TEMP_FILE_MAX_AGE
            for fname in os.listdir(tmp_dir):
                if (fname.startswith("soy_dev_") or fname.startswith("soy_deploy_")) and fname.endswith(".log"):
                    fpath = os.path.join(tmp_dir, fname)
                    if os.path.getmtime(fpath) < cutoff:
                        os.unlink(fpath)
        except Exception:
            pass

    # ── Slash Commands ──

    def _handle_slash(self, command, chat_id):
        """Handle slash commands directly (no AI). Returns True if handled."""
        cmd = command.split()[0].split("@")[0].lower()

        if cmd == "/start":
            with self._db() as conn:
                owner_row = conn.execute(
                    "SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name'"
                ).fetchone()
                project_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM projects WHERE status IN ('active', 'planning')"
                ).fetchone()["cnt"]
            name = owner_row["value"] if owner_row else "there"

            if project_count == 0:
                # Simplified welcome for new users
                self.send_message(chat_id,
                    f"Hey {name}!\n\n"
                    "SoY Telegram is live — running locally with full database access.\n\n"
                    "Text me tasks, ideas, or questions. Here's how to get started:\n\n"
                    "/new — create a new project from scratch\n"
                    "/status — project overview + task counts\n"
                    "/debug — bot diagnostics\n\n"
                    "*Example:*\n"
                    "`/new client-site Build a landing page with hero section`\n\n"
                    "_Send /start again later for all commands._"
                )
            else:
                self.send_message(chat_id,
                    f"Hey {name}!\n\n"
                    "SoY Telegram is live — running locally with full database access.\n\n"
                    "Text me tasks, ideas, or questions about your projects.\n\n"
                    "*Commands:*\n"
                    "/status — project overview + task counts\n"
                    "/tasks — open tasks (optionally filter by project)\n"
                    "/notes — recent notes\n"
                    "/new — create a new project from scratch\n"
                    "/delete — delete a project and clean up\n"
                    "/dev — spawn a remote dev session\n"
                    "/sessions — list recent dev sessions\n"
                    "/session — view session output\n"
                    "/approve — merge a session's branch to main\n"
                    "/reject — discard a session's branch\n"
                    "/kill — kill a running session\n"
                    "/debug — bot diagnostics\n"
                    "/errors — recent error log\n"
                    "/stop — shut down the bot"
                )
            return True

        if cmd == "/status":
            with self._db() as conn:
                projects = conn.execute(
                    "SELECT p.id, p.name, p.status, c.name as client, "
                    "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') as open_tasks, "
                    "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'done') as done_tasks, "
                    "(SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done' "
                    "AND t.due_date < date('now')) as overdue "
                    "FROM projects p LEFT JOIN contacts c ON c.id = p.client_id "
                    "WHERE p.status IN ('active', 'planning') ORDER BY p.name"
                ).fetchall()

            if not projects:
                self.send_message(chat_id,
                    "No active projects.\n\n"
                    "Create one with /new:\n"
                    "`/new <slug> <instruction>`\n\n"
                    "*Example:*\n"
                    "`/new client-site Build a landing page with hero section`")
                return True

            text = "*SoY Status*\n\n"
            for p in projects:
                overdue_tag = f" ({p['overdue']} overdue)" if p["overdue"] else ""
                client_tag = f"\n  Client: {p['client']}" if p["client"] else ""
                text += (
                    f"`{p['id']}` *{p['name']}* ({p['status']})\n"
                    f"  {p['open_tasks']} open, {p['done_tasks']} done{overdue_tag}{client_tag}\n\n"
                )
            self.send_message(chat_id, text.strip())
            return True

        if cmd == "/tasks":
            filter_text = command[len(cmd):].strip()
            with self._db() as conn:
                if filter_text:
                    tasks = conn.execute(
                        "SELECT t.title, t.priority, t.status, t.due_date, p.name as project_name "
                        "FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
                        "WHERE t.status != 'done' AND LOWER(p.name) LIKE LOWER(?) "
                        "ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
                        f"WHEN 'medium' THEN 2 ELSE 3 END LIMIT {TASK_DISPLAY_LIMIT}",
                        (f"%{filter_text}%",),
                    ).fetchall()
                    header = f"*Tasks — {filter_text}*\n\n"
                else:
                    tasks = conn.execute(
                        "SELECT t.title, t.priority, t.status, t.due_date, p.name as project_name "
                        "FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
                        "WHERE t.status != 'done' "
                        "ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
                        f"WHEN 'medium' THEN 2 ELSE 3 END LIMIT {TASK_DISPLAY_LIMIT}"
                    ).fetchall()
                    header = "*Open Tasks*\n\n"

            if not tasks:
                self.send_message(chat_id, "No open tasks." + (f" (filtered: {filter_text})" if filter_text else ""))
                return True

            text = header
            for t in tasks:
                pri_icon = PRIORITY_ICONS.get(t["priority"] or "medium", "🟡")
                proj = f" _{t['project_name']}_" if t["project_name"] else ""
                due = f" — due {t['due_date']}" if t["due_date"] else ""
                text += f"{pri_icon} {t['title']}{proj}{due}\n"

            self.send_message(chat_id, text.strip())
            return True

        if cmd == "/notes":
            search = command[len(cmd):].strip()
            with self._db() as conn:
                if search:
                    notes = conn.execute(
                        "SELECT title, SUBSTR(content, 1, 100) as content, linked_projects, created_at "
                        "FROM standalone_notes WHERE LOWER(title) LIKE LOWER(?) OR LOWER(content) LIKE LOWER(?) "
                        "ORDER BY created_at DESC LIMIT 20",
                        (f"%{search}%", f"%{search}%"),
                    ).fetchall()
                    header = f"*Notes — \"{search}\"*\n\n"
                else:
                    notes = conn.execute(
                        "SELECT title, SUBSTR(content, 1, 100) as content, linked_projects, created_at "
                        "FROM standalone_notes ORDER BY created_at DESC LIMIT 20"
                    ).fetchall()
                    header = "*Recent Notes*\n\n"

            if not notes:
                self.send_message(chat_id, "No notes found.")
                return True

            text = header
            for n in notes:
                proj = f" _{n['linked_projects']}_" if n["linked_projects"] else ""
                preview = f"\n  {n['content']}..." if n["content"] else ""
                text += f"• *{n['title']}*{proj}{preview}\n\n"

            self.send_message(chat_id, text.strip())
            return True

        if cmd == "/delete":
            args = command[len(cmd):].strip()
            self._handle_delete_project(args, chat_id)
            return True

        if cmd == "/new":
            args = command[len(cmd):].strip()
            self._handle_new_project(args, chat_id)
            return True

        if cmd == "/dev":
            args = command[len(cmd):].strip()
            model, args = self._extract_model_flag(args)

            if model not in ALLOWED_MODELS:
                self.send_message(chat_id,
                    f"❌ Unknown model: {model}. Use: {', '.join(sorted(ALLOWED_MODELS))}")
                return True

            if not args:
                self.send_message(chat_id,
                    "*Usage:* /dev <project> <instruction>\n\n"
                    "Example: /dev grow app Fix the nav bug on mobile\n\n"
                    f"Options: --model opus (default: {DEFAULT_MODEL})")
                return True

            # Check concurrent limit
            active_count = len(self.active_dev_sessions)
            if active_count >= DEV_SESSION_MAX_ACTIVE:
                self.send_message(chat_id,
                    f"❌ Max {DEV_SESSION_MAX_ACTIVE} concurrent sessions. "
                    f"Wait for one to finish or /kill one.")
                return True

            try:
                project_id, project_name, workspace, instruction = self._resolve_project_for_dev(args)
            except ValueError as e:
                self.send_message(chat_id, f"❌ {e}")
                return True

            # Ensure workspace has a git remote (auto-creates GitHub repo if missing)
            if not self._ensure_git_remote(workspace, project_name, chat_id):
                return True

            # Check for dirty workspace — prompt user before proceeding
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "-uno"],
                capture_output=True, text=True, cwd=workspace, timeout=5,
            ).stdout.strip()
            if dirty:
                self.send_message(chat_id,
                    f"⚠️ *{project_name}* has uncommitted changes:\n"
                    f"```\n{dirty[:500]}\n```\n\n"
                    "Reply *commit* to commit them first, *stash* to stash, or *cancel*.")
                self.pending_confirmations[chat_id] = {
                    "action": "dirty_workspace",
                    "project_id": project_id,
                    "project_name": project_name,
                    "workspace": workspace,
                    "instruction": instruction,
                    "model": model,
                    "expires_at": time.time() + CONFIRMATION_TIMEOUT,
                }
                return True

            self._launch_dev_session(project_id, project_name, workspace, instruction, chat_id, model)
            return True

        if cmd == "/sessions":
            with self._db() as conn:
                sessions = conn.execute(
                    "SELECT session_id, project_name, status, instruction, "
                    "duration_seconds, started_at, deploy_status, review_status "
                    "FROM telegram_dev_sessions ORDER BY started_at DESC LIMIT 10"
                ).fetchall()

            if not sessions:
                self.send_message(chat_id, "No dev sessions yet.")
                return True

            text = "*Recent Dev Sessions*\n\n"
            for s in sessions:
                icon = STATUS_ICONS.get(s["status"], "❓")
                duration = f" ({self._format_duration(s['duration_seconds'])})" if s["duration_seconds"] else ""
                instr_preview = s["instruction"][:50]
                if len(s["instruction"]) > 50:
                    instr_preview += "..."

                # Deploy + review badges
                badges = ""
                if s["deploy_status"]:
                    badges += f" {DEPLOY_ICONS.get(s['deploy_status'], '')}"
                if s["review_status"]:
                    badges += f" {REVIEW_ICONS.get(s['review_status'], '')}"

                text += (
                    f"{icon} `{s['session_id']}` — {s['project_name']}{badges}\n"
                    f"  {instr_preview}{duration}\n\n"
                )
            self.send_message(chat_id, text.strip())
            return True

        if cmd == "/session":
            session_arg = command[len(cmd):].strip()
            if not session_arg:
                self.send_message(chat_id, "*Usage:* /session <id>")
                return True

            with self._db() as conn:
                row, err = self._find_session_by_prefix(conn, session_arg)

            if not row:
                self.send_message(chat_id, err or f"No session found matching `{session_arg}`.")
                return True

            icon = STATUS_ICONS.get(row["status"], "❓")
            duration = self._format_duration(row["duration_seconds"]) if row["duration_seconds"] else ""

            text = (
                f"{icon} *Session `{row['session_id']}`*\n\n"
                f"*Project:* {row['project_name']}\n"
                f"*Status:* {row['status']}\n"
                f"*Model:* {row['model']}\n"
                f"*Instruction:* {row['instruction']}\n"
            )
            if duration:
                text += f"*Duration:* {duration}\n"
            if row["branch_name"]:
                text += f"*Branch:* `{row['branch_name']}`\n"
                # Show commit link if pushed to GitHub
                github_url = self._get_github_url(row["workspace_path"])
                if github_url:
                    text += f"📝 [Review code]({github_url}/tree/{row['branch_name']})\n"
            if row["review_status"]:
                review_label = {"pending": "⏳ Pending", "approved": "✅ Approved", "rejected": "🗑 Rejected"}
                text += f"*Review:* {review_label.get(row['review_status'], row['review_status'])}\n"
            if row["preview_url"]:
                text += f"*Preview:* {row['preview_url']}\n"
            elif row["deploy_status"]:
                deploy_label = {"deploying": "🚀 Deploying...", "deployed": "🌐 Deployed", "deploy_failed": "⚠️ Failed"}
                text += f"*Deploy:* {deploy_label.get(row['deploy_status'], row['deploy_status'])}\n"
            if row["git_diff_stat"]:
                text += f"\n*Changes:*\n```\n{row['git_diff_stat']}\n```\n"
            if row["output_summary"]:
                summary = row["output_summary"]
                if len(summary) > 2000:
                    summary = summary[:2000] + "..."
                text += f"\n*Output:*\n{summary}"
            elif row["status"] == "running":
                text += "\n_Still running..._"

            self.send_message(chat_id, text)
            return True

        if cmd == "/kill":
            session_arg = command[len(cmd):].strip()
            if not session_arg:
                self.send_message(chat_id, "*Usage:* /kill <id>")
                return True

            # Find in active sessions by prefix
            matches = [sid for sid in self.active_dev_sessions if sid.startswith(session_arg)]
            if len(matches) > 1:
                ids = ", ".join(f"`{s}`" for s in matches)
                self.send_message(chat_id,
                    f"Ambiguous prefix — matches {len(matches)} active sessions: {ids}\n"
                    "Use more characters to narrow it down.")
                return True
            matched_sid = matches[0] if matches else None

            if not matched_sid:
                # Check DB — session might exist but already finished
                with self._db() as conn:
                    row, err = self._find_session_by_prefix(conn, session_arg)
                if row:
                    self.send_message(chat_id,
                        f"Session `{row['session_id']}` ({row['project_name']}) "
                        f"already {row['status']} — nothing to kill.")
                else:
                    self.send_message(chat_id, err or f"No session found matching `{session_arg}`.")
                return True

            info = self.active_dev_sessions.pop(matched_sid)
            self.workspace_locks.discard(info.get("workspace"))
            proc = info["process"]
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

            try:
                info["stdout_file"].close()
            except Exception:
                pass

            # Also kill active deploy if one exists
            if matched_sid in self.active_deploys:
                deploy_info = self.active_deploys.pop(matched_sid)
                try:
                    deploy_info["process"].kill()
                    deploy_info["process"].wait(timeout=5)
                except Exception:
                    pass
                try:
                    deploy_info["stdout_file"].close()
                except Exception:
                    pass

            elapsed = int(time.time() - info["started_at"])
            with self._db() as conn:
                conn.execute(
                    "UPDATE telegram_dev_sessions SET status = 'killed', "
                    "completed_at = datetime('now'), duration_seconds = ?, "
                    "deploy_status = CASE WHEN deploy_status = 'deploying' THEN 'deploy_failed' ELSE deploy_status END "
                    "WHERE session_id = ?",
                    (elapsed, matched_sid),
                )
                conn.commit()

            self.send_message(chat_id, f"💀 Killed session `{matched_sid}` ({info['project_name']}).")
            return True

        if cmd == "/approve":
            session_arg = command[len(cmd):].strip()
            self._handle_approve(session_arg, chat_id)
            return True

        if cmd == "/reject":
            session_arg = command[len(cmd):].strip()
            self._handle_reject(session_arg, chat_id)
            return True

        if cmd == "/debug":
            uptime = ""
            if self.start_time:
                elapsed = int(time.time() - self.start_time)
                hours, remainder = divmod(elapsed, 3600)
                minutes, secs = divmod(remainder, 60)
                uptime = f"{hours}h {minutes}m {secs}s"

            last_claude = "never"
            if self.last_claude_call:
                ago = int(time.time() - self.last_claude_call)
                last_claude = f"{ago}s ago"

            active_dev = len(self.active_dev_sessions)
            text = (
                "*SoY Telegram Debug*\n\n"
                f"*Mode:* local (claude -p)\n"
                f"*Model:* {DEFAULT_MODEL}\n"
                f"*Python:* {sys.version.split()[0]}\n"
                f"*Uptime:* {uptime or 'unknown'}\n"
                f"*Messages:* {self.message_count}\n"
                f"*Last claude call:* {last_claude}\n"
                f"*Active dev sessions:* {active_dev}\n"
                f"*Session:* `{self.current_session_id or 'none'}`\n"
                f"*Owner ID:* `{OWNER_ID}`\n"
                f"*DB:* `{DB_PATH}`"
            )
            self.send_message(chat_id, text)
            return True

        if cmd == "/errors":
            with self._db() as conn:
                errors = conn.execute(
                    "SELECT error_message, user_message_preview, created_at "
                    "FROM telegram_bot_errors ORDER BY created_at DESC LIMIT 5"
                ).fetchall()

            if not errors:
                self.send_message(chat_id, "No errors recorded.")
                return True

            text = f"*Recent Errors* ({len(errors)})\n\n"
            for e in errors:
                text += (
                    f"• `{e['error_message']}`\n"
                    f"  {e['created_at']}"
                    + (f"\n  _{e['user_message_preview']}_" if e["user_message_preview"] else "")
                    + "\n\n"
                )
            self.send_message(chat_id, text.strip())
            return True

        if cmd == "/stop":
            # Kill all active dev sessions and deploys with a single DB connection
            with self._db() as conn:
                for sid, info in list(self.active_dev_sessions.items()):
                    try:
                        info["process"].kill()
                    except Exception:
                        pass
                    conn.execute(
                        "UPDATE telegram_dev_sessions SET status = 'killed', "
                        "completed_at = datetime('now') WHERE session_id = ?",
                        (sid,),
                    )
                for sid, info in list(self.active_deploys.items()):
                    try:
                        info["process"].kill()
                    except Exception:
                        pass
                    conn.execute(
                        "UPDATE telegram_dev_sessions SET deploy_status = 'deploy_failed', "
                        "deploy_pid = NULL WHERE session_id = ?",
                        (sid,),
                    )
                if self.active_dev_sessions or self.active_deploys:
                    conn.commit()
            self.active_dev_sessions.clear()
            self.active_deploys.clear()
            self.send_message(chat_id, "Shutting down. Bye!")
            self.running = False
            return True

        return False

    # ── Approve/Reject Handlers ──

    def _handle_approve(self, session_arg, chat_id):
        """Handle /approve — merge a session's branch to main."""
        if not session_arg:
            self.send_message(chat_id, "*Usage:* /approve <id>")
            return

        with self._db() as conn:
            row, err = self._find_session_by_prefix(conn, session_arg)

            if not row:
                self.send_message(chat_id, err or f"No session found matching `{session_arg}`.")
                return

            if not row["branch_name"]:
                self.send_message(chat_id, f"Session `{row['session_id']}` has no branch to merge.")
                return

            if row["review_status"] == "approved":
                self.send_message(chat_id, f"Session `{row['session_id']}` was already approved.")
                return

            if row["review_status"] == "rejected":
                self.send_message(chat_id, f"Session `{row['session_id']}` was already rejected (branch deleted).")
                return

            workspace = row["workspace_path"]
            branch = row["branch_name"]
            sid = row["session_id"]
            project_name = row["project_name"]

        # Acquire workspace lock
        if workspace in self.workspace_locks:
            self.send_message(chat_id,
                "This workspace is busy (dev session or approve/reject in progress). "
                "Wait for it to finish or /kill the session first.")
            return
        self.workspace_locks.add(workspace)

        try:
            subprocess.run(
                ["git", "checkout", "main"],
                capture_output=True, text=True, cwd=workspace, timeout=10,
                check=True,
            )
            merge_result = subprocess.run(
                ["git", "merge", branch, "--no-edit"],
                capture_output=True, text=True, cwd=workspace, timeout=30,
            )
            if merge_result.returncode != 0:
                error = merge_result.stderr.strip() or merge_result.stdout.strip()
                self.send_message(chat_id,
                    f"❌ Merge conflict on `{sid}`\n\n"
                    f"```\n{error[:500]}\n```\n\n"
                    "Resolve manually in the workspace, then try again.")
                subprocess.run(
                    ["git", "merge", "--abort"],
                    capture_output=True, text=True, cwd=workspace, timeout=10,
                )
                return

            # Delete the branch
            subprocess.run(
                ["git", "branch", "-d", branch],
                capture_output=True, text=True, cwd=workspace, timeout=10,
            )

            # Push to remote so Vercel picks it up
            push_result = subprocess.run(
                ["git", "push"],
                capture_output=True, text=True, cwd=workspace, timeout=30,
            )
            pushed = push_result.returncode == 0
        except subprocess.CalledProcessError as e:
            self.send_message(chat_id, f"❌ Git error: {e.stderr.strip() or e}")
            return
        except Exception as e:
            self.send_message(chat_id, f"❌ Error: {e}")
            return
        finally:
            self.workspace_locks.discard(workspace)

        with self._db() as conn:
            conn.execute(
                "UPDATE telegram_dev_sessions SET review_status = 'approved' "
                "WHERE session_id = ?", (sid,),
            )
            conn.commit()

        msg = (
            f"✅ *Approved* — `{sid}` merged to main\n"
            f"*Project:* {project_name}\n"
            f"Branch `{branch}` deleted."
        )
        if pushed:
            prod_url = self._get_vercel_production_url(workspace)
            if prod_url:
                msg += f"\n\n🚀 Production: {prod_url}"
                msg += "\n_(Vercel may take 1-2 min to deploy the new version)_"
            else:
                msg += "\n\nPushed to remote — Vercel will deploy automatically."
        else:
            push_err = push_result.stderr.strip() if push_result.stderr else ""
            msg += f"\n\n⚠️ Push failed — run `git push` manually.\n{push_err}"
        self.send_message(chat_id, msg)

    def _handle_reject(self, session_arg, chat_id):
        """Handle /reject — discard a session's branch."""
        if not session_arg:
            self.send_message(chat_id, "*Usage:* /reject <id>")
            return

        with self._db() as conn:
            row, err = self._find_session_by_prefix(conn, session_arg)

            if not row:
                self.send_message(chat_id, err or f"No session found matching `{session_arg}`.")
                return

            if not row["branch_name"]:
                self.send_message(chat_id, f"Session `{row['session_id']}` has no branch to reject.")
                return

            if row["review_status"] == "approved":
                self.send_message(chat_id, f"Session `{row['session_id']}` was already approved (merged).")
                return

            if row["review_status"] == "rejected":
                self.send_message(chat_id, f"Session `{row['session_id']}` was already rejected.")
                return

            workspace = row["workspace_path"]
            branch = row["branch_name"]
            sid = row["session_id"]
            project_name = row["project_name"]

        # Acquire workspace lock
        if workspace in self.workspace_locks:
            self.send_message(chat_id,
                "This workspace is busy (dev session or approve/reject in progress). "
                "Wait for it to finish or /kill the session first.")
            return
        self.workspace_locks.add(workspace)

        try:
            subprocess.run(
                ["git", "checkout", "main"],
                capture_output=True, text=True, cwd=workspace, timeout=10,
                check=True,
            )
            subprocess.run(
                ["git", "branch", "-D", branch],
                capture_output=True, text=True, cwd=workspace, timeout=10,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.send_message(chat_id, f"❌ Git error: {e.stderr.strip() or e}")
            return
        except Exception as e:
            self.send_message(chat_id, f"❌ Error: {e}")
            return
        finally:
            self.workspace_locks.discard(workspace)

        with self._db() as conn:
            conn.execute(
                "UPDATE telegram_dev_sessions SET review_status = 'rejected' "
                "WHERE session_id = ?", (sid,),
            )
            conn.commit()

        self.send_message(chat_id,
            f"🗑 *Rejected* — `{sid}` discarded\n"
            f"*Project:* {project_name}\n"
            f"Branch `{branch}` deleted. Main unchanged.")

    # ── Dev Request Detection ──

    _DEV_PATTERNS = re.compile(
        r'\b(?:'
        r'spin up.*(?:dev|claude|instance|session)'
        r'|(?:start|launch|run|kick off|fire up).*(?:dev session|claude|code session)'
        r'|(?:fix|build|implement|add|update|refactor|change|create|remove|delete|write)\b.*\b(?:bug|feature|component|page|code|function|test|style|css|html|api|endpoint|route|spinner|modal|button|form|layout|nav|header|footer|sidebar|dashboard|view|screen)'
        r'|make (?:a |the )?(?:code |)change'
        r'|dev (?:session|instance|work)'
        r')\b',
        re.IGNORECASE,
    )

    def _is_dev_request(self, text):
        """Detect natural language requests that should be /dev commands."""
        return bool(self._DEV_PATTERNS.search(text))

    def _suggest_dev_command(self, text, chat_id):
        """Guide the user to the /dev command."""
        with self._db() as conn:
            projects = conn.execute(
                "SELECT id, name, workspace_path FROM projects "
                "WHERE status IN ('active', 'planning') AND workspace_path IS NOT NULL "
                "ORDER BY name"
            ).fetchall()

        if not projects:
            self.send_message(chat_id,
                "No projects with workspaces set up. "
                "Add a workspace path to a project first.")
            return

        lines = [f"• `{p['id']}` — {p['name']}" for p in projects]

        self.send_message(chat_id,
            "Use /dev to start a dev session:\n"
            "`/dev <project> <instruction>`\n"
            "`/dev <id> <instruction>`\n\n"
            f"*Projects:*\n" + "\n".join(lines) + "\n\n"
            "Example:\n`/dev grow Fix the nav bug on mobile`")

    # ── Main Loop ──

    def run(self):
        """Main bot loop: long-poll for updates, process messages."""
        if not BOT_TOKEN:
            print("Error: TELEGRAM_BOT_TOKEN not set. Run /telegram-setup first.")
            sys.exit(1)
        if not OWNER_ID:
            print("Error: TELEGRAM_OWNER_ID not set. Run /telegram-setup first.")
            sys.exit(1)

        # Check required dependencies
        if not shutil.which("claude"):
            print("Error: `claude` CLI not found in PATH.")
            print("Install Claude Code: https://docs.anthropic.com/en/docs/claude-code")
            sys.exit(1)
        if not shutil.which("git"):
            print("Error: `git` not found in PATH (required for dev sessions).")
            sys.exit(1)

        # Validate token
        me = self._api("getMe")
        if not me.get("ok"):
            print(f"Error: Invalid bot token — {me.get('description', 'unknown error')}")
            sys.exit(1)

        bot_username = me["result"]["username"]

        # Delete any existing webhook (required for getUpdates to work)
        self._api("deleteWebhook")

        self.running = True
        self.start_time = time.time()
        offset = None

        # Recover orphaned dev sessions from previous runs
        self._recover_orphaned_sessions()
        # Clean up old temp files
        self._cleanup_old_temp_files()

        masked_id = f"{OWNER_ID[:3]}...{OWNER_ID[-2:]}" if len(OWNER_ID) > 5 else "***"
        print(f"SoY Telegram bot started — @{bot_username} (local mode, claude -p)")
        print(f"Owner ID: {masked_id}")
        print(f"Database: {DB_PATH}")
        print("Press Ctrl-C to stop.\n")

        # Signal handlers for graceful shutdown
        def handle_signal(signum, frame):
            print("\nShutting down...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                params = {"timeout": POLL_TIMEOUT, "allowed_updates": ["message", "callback_query"]}
                if offset is not None:
                    params["offset"] = offset

                updates = self._api("getUpdates", params)
                if not updates.get("ok"):
                    time.sleep(5)
                    continue

                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    self._process_update(update)

                # Check background dev sessions for completion
                if self.active_dev_sessions:
                    self._check_dev_sessions()

                # Check background deploys for completion
                if self.active_deploys:
                    self._check_deploys()

            except Exception as e:
                self._log_error(f"Poll loop error: {e}")
                time.sleep(5)

        # Clean up active processes on exit (Ctrl-C or SIGTERM)
        self._shutdown_active_processes()
        print("Bot stopped.")

    def _shutdown_active_processes(self):
        """Kill active dev sessions and deploys, update DB. Called on exit."""
        if not self.active_dev_sessions and not self.active_deploys:
            return
        with self._db() as conn:
            for sid, info in self.active_dev_sessions.items():
                try:
                    info["process"].kill()
                    info["process"].wait(timeout=5)
                except Exception:
                    pass
                try:
                    info["stdout_file"].close()
                except Exception:
                    pass
                conn.execute(
                    "UPDATE telegram_dev_sessions SET status = 'killed', "
                    "completed_at = datetime('now') WHERE session_id = ?",
                    (sid,),
                )
            for sid, info in self.active_deploys.items():
                try:
                    info["process"].kill()
                    info["process"].wait(timeout=5)
                except Exception:
                    pass
                try:
                    info["stdout_file"].close()
                except Exception:
                    pass
                conn.execute(
                    "UPDATE telegram_dev_sessions SET deploy_status = 'deploy_failed', "
                    "deploy_pid = NULL WHERE session_id = ?",
                    (sid,),
                )
            conn.commit()
        self.active_dev_sessions.clear()
        self.active_deploys.clear()

    def _process_update(self, update):
        """Process a single Telegram update."""
        # Handle callback queries (inline keyboard button presses)
        callback = update.get("callback_query")
        if callback:
            sender_id = str(callback.get("from", {}).get("id", ""))
            if sender_id != str(OWNER_ID):
                return
            chat_id = callback["message"]["chat"]["id"]
            data = callback.get("data", "")
            self._answer_callback(callback["id"])
            # Route callback data as a slash command (e.g. "approve:abc123" → "/approve abc123")
            if ":" in data:
                action, arg = data.split(":", 1)
                if action in ALLOWED_CALLBACK_ACTIONS:
                    self._handle_slash(f"/{action} {arg}", chat_id)
            return

        message = update.get("message")
        if not message or not message.get("text"):
            return

        # Security: owner check
        sender_id = str(message.get("from", {}).get("id", ""))
        if sender_id != str(OWNER_ID):
            return  # Silent ignore

        chat_id = message["chat"]["id"]
        text = message["text"].strip()
        msg_id = message.get("message_id")

        self.message_count += 1
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] Message #{self.message_count}: {text[:80]}{'...' if len(text) > 80 else ''}")

        try:
            # Check for pending confirmation before normal processing
            if chat_id in self.pending_confirmations:
                conf = self.pending_confirmations[chat_id]
                if time.time() > conf["expires_at"]:
                    del self.pending_confirmations[chat_id]
                    # Expired — fall through to normal processing
                else:
                    self._handle_pending_confirmation(text, chat_id)
                    return

            # Slash commands — handled directly, no AI
            if text.startswith("/"):
                if self._handle_slash(text, chat_id):
                    return

            # Intercept natural language dev requests → suggest /dev
            if self._is_dev_request(text):
                self._suggest_dev_command(text, chat_id)
                return

            # Natural language → claude -p
            self.send_typing(chat_id)
            session_id = self._get_or_create_session()
            self._save_message(session_id, "user", text, msg_id)

            response = self._call_claude(text, session_id)

            # Parse task/note markers
            tasks, notes, cleaned_response = self._parse_markers(response)

            # Capture items to local DB
            captured = []
            if tasks or notes:
                captured = self._capture_items(tasks, notes)

            # Build final response
            final = cleaned_response
            if captured:
                final += "\n\n_Captured:_\n" + "\n".join(f"• {c}" for c in captured)

            if not final.strip():
                final = "Done."

            self._save_message(session_id, "assistant", final)
            self.send_message(chat_id, final)

        except Exception as e:
            self._log_error(str(e), user_msg=text)
            self.send_message(chat_id, "Something went wrong processing that. Check /errors for details.")


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
