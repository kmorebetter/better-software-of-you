// Toggle client_completed flag on a task
export async function onRequestPatch(context) {
  const { id } = context.params;
  const db = context.env.DB;

  let body;
  try {
    body = await context.request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { client_completed, client_completed_by } = body;

  if (typeof client_completed !== "number" || (client_completed !== 0 && client_completed !== 1)) {
    return Response.json({ error: "client_completed must be 0 or 1" }, { status: 400 });
  }

  const task = await db.prepare("SELECT id, page_token FROM tasks WHERE id = ?").bind(id).first();
  if (!task) {
    return Response.json({ error: "Task not found" }, { status: 404 });
  }

  await db.prepare(
    `UPDATE tasks SET
      client_completed = ?,
      client_completed_at = CASE WHEN ? = 1 THEN datetime('now') ELSE NULL END,
      client_completed_by = ?,
      synced_to_soy = 0,
      updated_at = datetime('now')
    WHERE id = ?`
  ).bind(client_completed, client_completed, client_completed_by || null, id).run();

  return Response.json({ ok: true, id: Number(id), client_completed });
}
