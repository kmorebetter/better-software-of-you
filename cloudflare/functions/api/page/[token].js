// Hydration endpoint: returns tasks, notes, comments, suggestions for a page
export async function onRequestGet(context) {
  const { token } = context.params;
  const db = context.env.DB;

  const page = await db.prepare("SELECT token, title, owner_name FROM pages WHERE token = ?").bind(token).first();
  if (!page) {
    return Response.json({ error: "Page not found" }, { status: 404 });
  }

  const tasks = await db.prepare(
    "SELECT id, title, status, priority, client_completed, client_completed_by FROM tasks WHERE page_token = ? ORDER BY id"
  ).bind(token).all();

  const notes = await db.prepare(
    "SELECT id, section_id, content, author_name, created_at FROM notes WHERE page_token = ? ORDER BY created_at"
  ).bind(token).all();

  const comments = await db.prepare(
    "SELECT id, content, author_name, author_type, created_at FROM comments WHERE page_token = ? ORDER BY created_at"
  ).bind(token).all();

  const suggestions = await db.prepare(
    "SELECT id, title, description, suggested_by, status, created_at FROM suggestions WHERE page_token = ? ORDER BY created_at DESC"
  ).bind(token).all();

  return Response.json({
    page: { token: page.token, title: page.title, owner_name: page.owner_name },
    tasks: tasks.results || [],
    notes: notes.results || [],
    comments: comments.results || [],
    suggestions: suggestions.results || [],
  });
}
