// Telegram Webhook Handler for Software of You
// Receives messages from Telegram, processes via Claude API, responds.
// Security: webhook secret + IP allowlist + owner ID verification.

// Telegram webhook IP ranges (as of 2024)
const TELEGRAM_IP_RANGES = [
  { prefix: [149, 154, 160], mask: 20 },  // 149.154.160.0/20
  { prefix: [91, 108, 4], mask: 22 },     // 91.108.4.0/22
];

function ipInRange(ip, range) {
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4) return false;
  const ipNum = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3];
  const prefixParts = range.prefix;
  const prefixNum =
    (prefixParts[0] << 24) | (prefixParts[1] << 16) | ((prefixParts[2] || 0) << 8) | (prefixParts[3] || 0);
  const maskBits = (~0 << (32 - range.mask)) >>> 0;
  return (ipNum & maskBits) === (prefixNum & maskBits);
}

function isTelegramIP(ip) {
  return TELEGRAM_IP_RANGES.some((range) => ipInRange(ip, range));
}

// ── Tool Definitions for Claude ──

const TOOL_DEFINITIONS = [
  {
    name: "add_task",
    description:
      "Capture a task to the backlog. Use when the user wants to remember something to do, a bug to fix, a feature to build, etc.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Short task title" },
        description: { type: "string", description: "Optional longer description" },
        project_name: {
          type: "string",
          description: "Project name to associate with (must match a known project name). Omit if unclear.",
        },
        priority: {
          type: "string",
          enum: ["low", "medium", "high", "urgent"],
          description: "Task priority. Default medium.",
        },
      },
      required: ["title"],
    },
  },
  {
    name: "add_note",
    description:
      "Capture a note or idea. Use when the user shares a thought, insight, decision rationale, or anything worth remembering that isn't a task.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Note title" },
        content: { type: "string", description: "Note content/body" },
        project_name: {
          type: "string",
          description: "Project name to associate with (must match a known project name). Omit if unclear.",
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Optional tags for categorization",
        },
      },
      required: ["title"],
    },
  },
  {
    name: "get_projects",
    description: "List all projects with their current status and task counts.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "get_tasks",
    description: "List tasks, optionally filtered by project name.",
    input_schema: {
      type: "object",
      properties: {
        project_name: { type: "string", description: "Filter by project name (partial match)" },
        status: {
          type: "string",
          enum: ["open", "done", "all"],
          description: "Filter by status. Default: open",
        },
      },
    },
  },
  {
    name: "get_notes",
    description: "List or search notes.",
    input_schema: {
      type: "object",
      properties: {
        search: { type: "string", description: "Search term to filter notes" },
        project_name: { type: "string", description: "Filter by project name" },
      },
    },
  },
  {
    name: "search_context",
    description:
      "Full-text search across all cached SoY data (projects, tasks, notes, contacts). Use when the user asks a question about their data.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
      },
      required: ["query"],
    },
  },
];

// ── Tool Execution ──

async function executeTool(db, toolName, toolInput, messageId) {
  switch (toolName) {
    case "add_task":
      return await addTask(db, toolInput, messageId);
    case "add_note":
      return await addNote(db, toolInput, messageId);
    case "get_projects":
      return await getProjects(db);
    case "get_tasks":
      return await getTasks(db, toolInput);
    case "get_notes":
      return await getNotes(db, toolInput);
    case "search_context":
      return await searchContext(db, toolInput);
    default:
      return { error: `Unknown tool: ${toolName}` };
  }
}

async function addTask(db, input, messageId) {
  const { title, description, project_name, priority } = input;
  const stmt = await db
    .prepare(
      "INSERT INTO telegram_backlog (type, title, content, project_name, priority, source_message_id) VALUES ('task', ?, ?, ?, ?, ?)"
    )
    .bind(title, description || null, project_name || null, priority || "medium", messageId || null)
    .run();
  return {
    success: true,
    id: stmt.meta.last_row_id,
    message: `Task captured: "${title}"${project_name ? ` (${project_name})` : ""}`,
  };
}

async function addNote(db, input, messageId) {
  const { title, content, project_name, tags } = input;
  const stmt = await db
    .prepare(
      "INSERT INTO telegram_backlog (type, title, content, project_name, tags, source_message_id) VALUES ('note', ?, ?, ?, ?, ?)"
    )
    .bind(title, content || null, project_name || null, tags ? JSON.stringify(tags) : null, messageId || null)
    .run();
  return {
    success: true,
    id: stmt.meta.last_row_id,
    message: `Note captured: "${title}"${project_name ? ` (${project_name})` : ""}`,
  };
}

async function getProjects(db) {
  const ctx = await db.prepare("SELECT value FROM telegram_context WHERE key = 'projects'").first();
  if (!ctx) return { projects: [], message: "No project data cached. Run sync to update." };
  try {
    return { projects: JSON.parse(ctx.value) };
  } catch {
    return { projects: [], message: "Failed to parse project data." };
  }
}

async function getTasks(db, input) {
  const { project_name, status } = input || {};

  // Include both cached tasks and unsent backlog tasks
  const cached = await db.prepare("SELECT value FROM telegram_context WHERE key = 'tasks'").first();
  let tasks = [];
  if (cached) {
    try {
      tasks = JSON.parse(cached.value);
    } catch {}
  }

  // Add unsynced backlog tasks
  const backlog = await db
    .prepare("SELECT title, priority, project_name, created_at FROM telegram_backlog WHERE type = 'task' AND synced_to_soy = 0")
    .all();
  for (const item of backlog.results || []) {
    tasks.push({
      title: item.title,
      priority: item.priority,
      project_name: item.project_name,
      status: "pending (backlog)",
      source: "telegram",
    });
  }

  // Filter
  if (project_name) {
    const q = project_name.toLowerCase();
    tasks = tasks.filter((t) => (t.project_name || "").toLowerCase().includes(q));
  }
  if (status && status !== "all") {
    if (status === "done") {
      tasks = tasks.filter((t) => (t.status || "").toLowerCase().includes("done") || (t.status || "").toLowerCase().includes("complete"));
    } else {
      tasks = tasks.filter((t) => !(t.status || "").toLowerCase().includes("done") && !(t.status || "").toLowerCase().includes("complete"));
    }
  }

  return { tasks, count: tasks.length };
}

async function getNotes(db, input) {
  const { search, project_name } = input || {};
  const cached = await db.prepare("SELECT value FROM telegram_context WHERE key = 'notes'").first();
  let notes = [];
  if (cached) {
    try {
      notes = JSON.parse(cached.value);
    } catch {}
  }

  // Add unsynced backlog notes
  const backlog = await db
    .prepare("SELECT title, content, project_name, tags, created_at FROM telegram_backlog WHERE type = 'note' AND synced_to_soy = 0")
    .all();
  for (const item of backlog.results || []) {
    notes.push({
      title: item.title,
      content: item.content,
      project_name: item.project_name,
      tags: item.tags,
      source: "telegram",
    });
  }

  if (search) {
    const q = search.toLowerCase();
    notes = notes.filter(
      (n) =>
        (n.title || "").toLowerCase().includes(q) ||
        (n.content || "").toLowerCase().includes(q) ||
        (n.tags || "").toLowerCase().includes(q)
    );
  }
  if (project_name) {
    const q = project_name.toLowerCase();
    notes = notes.filter((n) => (n.project_name || "").toLowerCase().includes(q));
  }

  return { notes, count: notes.length };
}

async function searchContext(db, input) {
  const { query } = input;
  if (!query) return { results: [], message: "No query provided." };

  const q = query.toLowerCase();
  const results = [];

  // Search all context keys
  const rows = await db.prepare("SELECT key, value FROM telegram_context").all();
  for (const row of rows.results || []) {
    try {
      const data = JSON.parse(row.value);
      if (Array.isArray(data)) {
        for (const item of data) {
          const text = JSON.stringify(item).toLowerCase();
          if (text.includes(q)) {
            results.push({ type: row.key, ...item });
          }
        }
      }
    } catch {}
  }

  // Also search backlog
  const backlog = await db
    .prepare(
      "SELECT type, title, content, project_name FROM telegram_backlog WHERE synced_to_soy = 0 AND (LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
    )
    .bind(`%${q}%`, `%${q}%`)
    .all();
  for (const item of backlog.results || []) {
    results.push({ type: "backlog_" + item.type, ...item, source: "telegram" });
  }

  return { results, count: results.length, query };
}

// ── Session Management ──

async function getOrCreateSession(db) {
  // Find active session (last message within 4 hours)
  const cutoff = new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString().replace("T", " ").slice(0, 19);
  const active = await db
    .prepare("SELECT id, message_count FROM telegram_sessions WHERE last_message_at > ? ORDER BY last_message_at DESC LIMIT 1")
    .bind(cutoff)
    .first();

  if (active) {
    await db
      .prepare("UPDATE telegram_sessions SET last_message_at = datetime('now'), message_count = message_count + 1 WHERE id = ?")
      .bind(active.id)
      .run();
    return { id: active.id, isNew: false, messageCount: active.message_count + 1 };
  }

  // Create new session
  const sessionId = crypto.randomUUID();
  await db
    .prepare("INSERT INTO telegram_sessions (id) VALUES (?)")
    .bind(sessionId)
    .run();
  return { id: sessionId, isNew: true, messageCount: 1 };
}

async function getConversationHistory(db, sessionId, limit = 20) {
  const rows = await db
    .prepare("SELECT role, content FROM telegram_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?")
    .bind(sessionId, limit)
    .all();
  // Reverse to get chronological order
  return (rows.results || []).reverse();
}

async function saveMessage(db, sessionId, role, content, telegramMessageId, toolCalls, toolResults) {
  await db
    .prepare(
      "INSERT INTO telegram_messages (session_id, role, content, telegram_message_id, tool_calls, tool_results) VALUES (?, ?, ?, ?, ?, ?)"
    )
    .bind(
      sessionId,
      role,
      content,
      telegramMessageId || null,
      toolCalls ? JSON.stringify(toolCalls) : null,
      toolResults ? JSON.stringify(toolResults) : null
    )
    .run();
}

// ── System Prompt ──

async function buildSystemPrompt(db, env) {
  const ownerName = env.SOY_OWNER_NAME || "there";

  // Load context snapshot
  let projectsCtx = "No project data cached yet.";
  let tasksCtx = "No task data cached yet.";
  let contactsCtx = "No contact data cached yet.";
  let metaCtx = "";

  const contextRows = await db.prepare("SELECT key, value FROM telegram_context").all();
  for (const row of contextRows.results || []) {
    try {
      const data = JSON.parse(row.value);
      if (row.key === "projects" && Array.isArray(data) && data.length > 0) {
        projectsCtx = data
          .map((p) => `- ${p.name} (${p.status}) — ${p.open_tasks || 0} open tasks, ${p.done_tasks || 0} done${p.client ? `, client: ${p.client}` : ""}`)
          .join("\n");
      } else if (row.key === "tasks" && Array.isArray(data) && data.length > 0) {
        tasksCtx = data
          .map((t) => `- [${t.priority || "medium"}] ${t.title}${t.project_name ? ` (${t.project_name})` : ""}${t.due_date ? ` — due ${t.due_date}` : ""}`)
          .join("\n");
      } else if (row.key === "contacts" && Array.isArray(data) && data.length > 0) {
        contactsCtx = data
          .map((c) => `- ${c.name}${c.company ? ` — ${c.company}` : ""}${c.role ? ` (${c.role})` : ""}`)
          .join("\n");
      } else if (row.key === "meta") {
        metaCtx = typeof data === "string" ? data : JSON.stringify(data);
      }
    } catch {}
  }

  // Count pending backlog items
  const pendingCount = await db
    .prepare("SELECT COUNT(*) as count FROM telegram_backlog WHERE synced_to_soy = 0")
    .first();

  return `You are the Telegram interface for Software of You — ${ownerName}'s personal data platform.

You have two modes:
1. **Backlog mode**: Quickly capture tasks and notes. Confirm briefly, move on. Don't over-ask for details.
2. **Chat mode**: Answer questions about projects, tasks, contacts using your tools. Ground answers in actual data.

Keep responses concise — this is Telegram, not a desktop app. Use short paragraphs, not walls of text.

## ${ownerName}'s Projects
${projectsCtx}

## Open Tasks
${tasksCtx}

## Key Contacts
${contactsCtx}

${metaCtx ? `## Additional Context\n${metaCtx}` : ""}

## Pending Backlog
${pendingCount ? pendingCount.count : 0} items waiting to sync to local SoY.

## Guidelines
- When the user shares an idea or TODO, capture it immediately with add_task or add_note. Don't ask "would you like me to save that?" — just do it and confirm.
- Match project names to known projects when obvious. If ambiguous, ask.
- For questions about data, use search_context or the relevant get_ tool.
- Never fabricate data. If something isn't in your context, say so.
- Be warm but efficient. This is a mobile conversation.`;
}

// ── Claude API ──

async function callClaude(messages, systemPrompt, env) {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1024,
      system: systemPrompt,
      tools: TOOL_DEFINITIONS,
      messages,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Claude API ${response.status}: ${errorText.slice(0, 200)}`);
  }

  return response.json();
}

// ── Telegram API ──

async function sendTelegramMessage(chatId, text, env) {
  // Split at paragraph boundaries if >4096 chars
  const MAX_LEN = 4096;
  const chunks = [];

  if (text.length <= MAX_LEN) {
    chunks.push(text);
  } else {
    let remaining = text;
    while (remaining.length > 0) {
      if (remaining.length <= MAX_LEN) {
        chunks.push(remaining);
        break;
      }
      // Find last paragraph break within limit
      let splitIdx = remaining.lastIndexOf("\n\n", MAX_LEN);
      if (splitIdx < MAX_LEN / 2) {
        // No good paragraph break, try single newline
        splitIdx = remaining.lastIndexOf("\n", MAX_LEN);
      }
      if (splitIdx < MAX_LEN / 2) {
        // No good break at all, hard split
        splitIdx = MAX_LEN;
      }
      chunks.push(remaining.slice(0, splitIdx));
      remaining = remaining.slice(splitIdx).trimStart();
    }
  }

  for (const chunk of chunks) {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: chunk,
        parse_mode: "Markdown",
      }),
    });
  }
}

// ── Slash Commands (handled without Claude API) ──

async function handleSlashCommand(command, chatId, db, env) {
  switch (command) {
    case "/start": {
      const ownerName = env.SOY_OWNER_NAME || "there";
      await sendTelegramMessage(
        chatId,
        `Hey ${ownerName} \u{1F44B}\n\nSoY Telegram is live. Text me tasks, ideas, or questions about your projects — I've got your full context.\n\nQuick commands:\n/status — project overview\n/backlog — pending items`,
        env
      );
      return true;
    }

    case "/status": {
      const projects = await db.prepare("SELECT value FROM telegram_context WHERE key = 'projects'").first();
      const meta = await db.prepare("SELECT value FROM telegram_context WHERE key = 'meta'").first();
      const pending = await db
        .prepare("SELECT COUNT(*) as count FROM telegram_backlog WHERE synced_to_soy = 0")
        .first();

      let statusText = "*SoY Status*\n\n";

      if (projects) {
        try {
          const projectList = JSON.parse(projects.value);
          statusText += "*Projects:*\n";
          for (const p of projectList) {
            statusText += `\u{2022} ${p.name} (${p.status}) — ${p.open_tasks || 0} open, ${p.done_tasks || 0} done\n`;
          }
        } catch {
          statusText += "No project data cached.\n";
        }
      } else {
        statusText += "No project data cached.\n";
      }

      statusText += `\n*Backlog:* ${pending ? pending.count : 0} items pending sync`;

      if (meta) {
        try {
          const metaData = JSON.parse(meta.value);
          if (metaData.last_sync) {
            statusText += `\n*Last sync:* ${metaData.last_sync}`;
          }
        } catch {}
      }

      await sendTelegramMessage(chatId, statusText, env);
      return true;
    }

    case "/backlog": {
      const items = await db
        .prepare(
          "SELECT type, title, project_name, priority, created_at FROM telegram_backlog WHERE synced_to_soy = 0 ORDER BY created_at DESC LIMIT 20"
        )
        .all();

      if (!items.results || items.results.length === 0) {
        await sendTelegramMessage(chatId, "Backlog is empty \u{2705} Everything has been synced.", env);
        return true;
      }

      let text = `*Pending Backlog* (${items.results.length} items)\n\n`;
      for (const item of items.results) {
        const icon = item.type === "task" ? "\u{2611}\u{FE0F}" : "\u{1F4DD}";
        const proj = item.project_name ? ` _${item.project_name}_` : "";
        text += `${icon} ${item.title}${proj}\n`;
      }
      text += "\nThese will sync to your local SoY on next sync.";
      await sendTelegramMessage(chatId, text, env);
      return true;
    }

    default:
      return false;
  }
}

// ── Main Handler ──

export async function onRequestPost(context) {
  const { env, request } = context;
  const db = env.DB;

  // ── Security Layer 1: Webhook Secret ──
  const secretHeader = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (!secretHeader || secretHeader !== env.TELEGRAM_WEBHOOK_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }

  // ── Security Layer 2: IP Allowlist ──
  const clientIP = request.headers.get("CF-Connecting-IP") || "";
  if (!isTelegramIP(clientIP)) {
    return new Response("Forbidden", { status: 403 });
  }

  // Parse the update
  let update;
  try {
    update = await request.json();
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  // Only handle text messages
  const message = update.message;
  if (!message || !message.text) {
    return new Response("OK", { status: 200 });
  }

  // ── Security Layer 3: Owner ID ──
  const senderId = String(message.from?.id || "");
  if (senderId !== String(env.TELEGRAM_OWNER_ID)) {
    // Silent 200 — reveal nothing
    return new Response("OK", { status: 200 });
  }

  const chatId = message.chat.id;
  const text = message.text.trim();
  const telegramMessageId = message.message_id;

  try {
    // ── Slash Commands ──
    if (text.startsWith("/")) {
      const cmd = text.split(" ")[0].split("@")[0].toLowerCase();
      const handled = await handleSlashCommand(cmd, chatId, db, env);
      if (handled) return new Response("OK", { status: 200 });
    }

    // ── Session Management ──
    const session = await getOrCreateSession(db);

    // Save user message
    await saveMessage(db, session.id, "user", text, telegramMessageId);

    // Build conversation for Claude
    const history = await getConversationHistory(db, session.id);
    const claudeMessages = history.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Build system prompt
    const systemPrompt = await buildSystemPrompt(db, env);

    // ── Claude API Call ──
    let response = await callClaude(claudeMessages, systemPrompt, env);

    // ── Handle Tool Use ──
    let iterations = 0;
    const maxIterations = 5;

    while (response.stop_reason === "tool_use" && iterations < maxIterations) {
      iterations++;
      const toolBlocks = response.content.filter((b) => b.type === "tool_use");
      const toolResults = [];

      for (const toolBlock of toolBlocks) {
        const result = await executeTool(db, toolBlock.name, toolBlock.input, telegramMessageId);
        toolResults.push({
          type: "tool_result",
          tool_use_id: toolBlock.id,
          content: JSON.stringify(result),
        });
      }

      // Continue conversation with tool results
      claudeMessages.push({ role: "assistant", content: response.content });
      claudeMessages.push({ role: "user", content: toolResults });

      response = await callClaude(claudeMessages, systemPrompt, env);
    }

    // Extract final text response
    const textBlocks = response.content.filter((b) => b.type === "text");
    const replyText = textBlocks.map((b) => b.text).join("\n\n") || "Done.";

    // Save assistant response
    await saveMessage(db, session.id, "assistant", replyText, null);

    // Send to Telegram
    await sendTelegramMessage(chatId, replyText, env);
  } catch (err) {
    // Send error to user without exposing internals
    try {
      await sendTelegramMessage(chatId, "Something went wrong processing that. Try again in a moment.", env);
    } catch {}
  }

  return new Response("OK", { status: 200 });
}

// Reject non-POST
export async function onRequestGet() {
  return new Response("Method Not Allowed", { status: 405 });
}
