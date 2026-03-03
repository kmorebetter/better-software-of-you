// List and add comments for a page

// GET /api/comments?page_token=xxx
export async function onRequestGet(context) {
  const db = context.env.DB;
  const url = new URL(context.request.url);
  const page_token = url.searchParams.get("page_token");

  if (!page_token) {
    return Response.json({ error: "page_token query param is required" }, { status: 400 });
  }

  const comments = await db.prepare(
    "SELECT id, content, author_name, author_type, created_at FROM comments WHERE page_token = ? ORDER BY created_at"
  ).bind(page_token).all();

  return Response.json({ comments: comments.results || [] });
}

// POST /api/comments
export async function onRequestPost(context) {
  const db = context.env.DB;

  let body;
  try {
    body = await context.request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { page_token, content, author_name, author_type } = body;

  if (!page_token || !content) {
    return Response.json({ error: "page_token and content are required" }, { status: 400 });
  }

  const page = await db.prepare("SELECT token FROM pages WHERE token = ?").bind(page_token).first();
  if (!page) {
    return Response.json({ error: "Page not found" }, { status: 404 });
  }

  const type = author_type === "owner" ? "owner" : "client";

  const result = await db.prepare(
    "INSERT INTO comments (page_token, content, author_name, author_type) VALUES (?, ?, ?, ?)"
  ).bind(page_token, content, author_name || "Client", type).run();

  return Response.json({
    ok: true,
    id: result.meta.last_row_id,
    content,
    author_name: author_name || "Client",
    author_type: type,
  }, { status: 201 });
}
