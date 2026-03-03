// Serve published page HTML from D1 with optional email-gated access control.
//
// Flow:
//   GET + no access control on page     → serve HTML directly (backward compat)
//   GET + access control + valid cookie  → serve HTML
//   GET + access control + no cookie     → serve auth gate page
//   POST                                 → email verification → set session cookie

const COOKIE_MAX_AGE = 90 * 24 * 60 * 60; // 90 days in seconds

function parseCookies(header) {
  const cookies = {};
  if (!header) return cookies;
  header.split(";").forEach((c) => {
    const [k, ...v] = c.trim().split("=");
    if (k) cookies[k.trim()] = v.join("=").trim();
  });
  return cookies;
}

function cookieName(token) {
  return `soy_session_${token}`;
}

// ── GET handler ──────────────────────────────────────────────────

export async function onRequestGet(context) {
  const { token } = context.params;
  const db = context.env.DB;

  const page = await db
    .prepare("SELECT html, title, owner_email FROM pages WHERE token = ?")
    .bind(token)
    .first();

  if (!page) {
    return new Response("Page not found", {
      status: 404,
      headers: { "Content-Type": "text/plain" },
    });
  }

  // Check if this page has access control
  const accessRow = await db
    .prepare("SELECT COUNT(*) as cnt FROM page_access WHERE page_token = ?")
    .bind(token)
    .first();

  const hasAccessControl = accessRow && accessRow.cnt > 0;

  // No access control → serve directly (backward compatible)
  if (!hasAccessControl) {
    return servePage(page.html, page.owner_email);
  }

  // Access control exists → check for valid session cookie
  const cookies = parseCookies(context.request.headers.get("Cookie"));
  const sessionId = cookies[cookieName(token)];

  if (sessionId) {
    const session = await db
      .prepare(
        "SELECT email FROM sessions WHERE session_id = ? AND page_token = ? AND expires_at > datetime('now')"
      )
      .bind(sessionId, token)
      .first();

    if (session) {
      return servePage(page.html, page.owner_email, session.email);
    }
  }

  // No valid session → serve the auth gate
  return new Response(authGateHTML(page.title), {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-cache, no-store, must-revalidate",
    },
  });
}

// ── POST handler: email verification ─────────────────────────────

export async function onRequestPost(context) {
  const { token } = context.params;
  const db = context.env.DB;

  let body;
  try {
    body = await context.request.json();
  } catch {
    return jsonResponse({ error: "Invalid request" }, 400);
  }

  const email = (body.email || "").trim().toLowerCase();
  if (!email) {
    return jsonResponse({ error: "Email is required" }, 400);
  }

  // Check page exists
  const page = await db
    .prepare("SELECT token FROM pages WHERE token = ?")
    .bind(token)
    .first();

  if (!page) {
    return jsonResponse({ error: "Page not found" }, 404);
  }

  // Check if this email has access
  const access = await db
    .prepare(
      "SELECT email FROM page_access WHERE page_token = ? AND LOWER(email) = ?"
    )
    .bind(token, email)
    .first();

  if (!access) {
    return jsonResponse(
      { error: "This page wasn't shared with you." },
      403
    );
  }

  // Create session
  const sessionId = crypto.randomUUID();
  const expiresAt = new Date(Date.now() + COOKIE_MAX_AGE * 1000).toISOString();

  await db
    .prepare(
      "INSERT INTO sessions (session_id, page_token, email, expires_at) VALUES (?, ?, ?, ?)"
    )
    .bind(sessionId, token, email, expiresAt)
    .run();

  // Set cookie and return success
  const cookie = [
    `${cookieName(token)}=${sessionId}`,
    `Path=/p/${token}`,
    `Max-Age=${COOKIE_MAX_AGE}`,
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
  ].join("; ");

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": cookie,
    },
  });
}

// ── Helpers ──────────────────────────────────────────────────────

function servePage(html, ownerEmail, sessionEmail) {
  // Inject owner email and session email so client-side JS can detect the page owner
  const vars = [];
  if (ownerEmail) vars.push(`window.__SOY_OWNER_EMAIL__=${JSON.stringify(ownerEmail.toLowerCase())}`);
  if (sessionEmail) vars.push(`window.__SOY_SESSION_EMAIL__=${JSON.stringify(sessionEmail.toLowerCase())}`);
  if (vars.length) {
    const script = `<script>${vars.join(";")}</script>`;
    html = html.replace("</head>", `${script}\n</head>`);
  }
  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "X-Robots-Tag": "noindex, nofollow",
      "Cache-Control": "no-cache, no-store, must-revalidate",
    },
  });
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authGateHTML(pageTitle) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow">
  <title>${escHtml(pageTitle)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-zinc-50 min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <div class="bg-white rounded-2xl border border-zinc-200 shadow-sm p-8 text-center">
      <!-- Lock icon -->
      <div class="mx-auto w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mb-5">
        <svg class="w-6 h-6 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>

      <h1 class="text-lg font-semibold text-zinc-900 mb-1">${escHtml(pageTitle)}</h1>
      <p class="text-sm text-zinc-500 mb-6">Enter your email to view this page.</p>

      <form id="auth-form" class="space-y-3">
        <input type="email" id="email-input" required
          placeholder="your@email.com"
          class="w-full px-4 py-2.5 border border-zinc-300 rounded-xl text-sm
                 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent
                 placeholder:text-zinc-400" />
        <button type="submit" id="submit-btn"
          class="w-full py-2.5 bg-zinc-900 text-white text-sm font-medium rounded-xl
                 hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          Continue
        </button>
      </form>

      <p id="error-msg" class="hidden mt-4 text-sm text-red-600"></p>
    </div>

    <p class="text-center text-xs text-zinc-400 mt-4">
      This page was shared with you privately.
    </p>
  </div>

  <script>
    document.getElementById("auth-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("submit-btn");
      const err = document.getElementById("error-msg");
      const email = document.getElementById("email-input").value.trim();

      btn.disabled = true;
      btn.textContent = "Checking...";
      err.classList.add("hidden");

      try {
        const resp = await fetch(window.location.pathname, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const data = await resp.json();

        if (data.ok) {
          localStorage.setItem("soy-auth-email", email.toLowerCase());
          window.location.reload();
        } else {
          err.textContent = data.error || "Access denied.";
          err.classList.remove("hidden");
          btn.disabled = false;
          btn.textContent = "Continue";
        }
      } catch {
        err.textContent = "Something went wrong. Try again.";
        err.classList.remove("hidden");
        btn.disabled = false;
        btn.textContent = "Continue";
      }
    });
  </script>
</body>
</html>`;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
