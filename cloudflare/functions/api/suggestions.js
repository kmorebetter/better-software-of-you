// Submit a task suggestion
export async function onRequestPost(context) {
  const db = context.env.DB;

  let body;
  try {
    body = await context.request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { page_token, title, description, suggested_by } = body;

  if (!page_token || !title) {
    return Response.json({ error: "page_token and title are required" }, { status: 400 });
  }

  const page = await db.prepare("SELECT token FROM pages WHERE token = ?").bind(page_token).first();
  if (!page) {
    return Response.json({ error: "Page not found" }, { status: 404 });
  }

  const result = await db.prepare(
    "INSERT INTO suggestions (page_token, title, description, suggested_by) VALUES (?, ?, ?, ?)"
  ).bind(page_token, title, description || null, suggested_by || "Client").run();

  return Response.json({
    ok: true,
    id: result.meta.last_row_id,
    title,
    status: "pending",
  }, { status: 201 });
}
