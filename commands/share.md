---
description: Create a client-safe version of any generated page — strips internal elements, ready to email or share
allowed-tools: ["Bash", "Read"]
argument-hint: <page name, project name, or filename>
---

# Share — Client-Safe Page Export

Create a clean, shareable version of a generated HTML page. Strips all internal SoY elements (sidebar, dark mode, AI analysis cards, interactive buttons, internal navigation) while keeping all content, styling, and animations.

## Step 1: Resolve the Page

Match `$ARGUMENTS` against the `generated_views` table. Try entity_name, filename, and view_type:

```sql
SELECT id, view_type, entity_type, entity_name, filename
FROM generated_views
WHERE entity_name LIKE '%$ARGUMENTS%'
   OR filename LIKE '%$ARGUMENTS%'
   OR view_type LIKE '%$ARGUMENTS%'
ORDER BY updated_at DESC;
```

**If no match:** Show available pages in a table and ask the user which one to share.

**If multiple matches:** Show the matches and ask the user to pick one. Prefer `entity_page` and `pm_report` view types over others.

**If single match:** Proceed.

## Step 2: Get User Name

```sql
SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name';
```

## Step 3: Run the Export

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/export_page.py" \
  "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/<filename>" \
  --user-name "<user_name>"
```

The script outputs JSON with `input`, `output`, `title`, and `size_kb`.

## Step 4: Log Activity

```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('<entity_type>', <entity_id>, 'page_shared',
        'Created client-safe export: <filename>', datetime('now'));
```

## Step 5: Open the File

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/open_page.sh" --share <filename>
```

## Step 6: Confirm

Tell the user:

> Client-safe version of **{entity_name}** saved to `output/share/{filename}` ({size_kb}KB).
> You can email this file directly or share it via Google Drive — it's fully self-contained.

If the hub server is running, also mention: `http://localhost:8787/share/{filename}`
