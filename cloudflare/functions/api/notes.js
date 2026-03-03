// Add a section note
export async function onRequestPost(context) {
  const db = context.env.DB;

  let body;
  try {
    body = await context.request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { page_token, section_id, content, author_name } = body;

  if (!page_token || !section_id || !content) {
    return Response.json({ error: "page_token, section_id, and content are required" }, { status: 400 });
  }

  const page = await db.prepare("SELECT token FROM pages WHERE token = ?").bind(page_token).first();
  if (!page) {
    return Response.json({ error: "Page not found" }, { status: 404 });
  }

  const result = await db.prepare(
    "INSERT INTO notes (page_token, section_id, content, author_name) VALUES (?, ?, ?, ?)"
  ).bind(page_token, section_id, content, author_name || "Client").run();

  return Response.json({
    ok: true,
    id: result.meta.last_row_id,
    section_id,
    content,
    author_name: author_name || "Client",
  }, { status: 201 });
}
