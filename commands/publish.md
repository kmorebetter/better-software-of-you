---
description: Publish a project page as a live interactive document — clients can check tasks, leave notes, comment, and suggest tasks. Optionally share with a specific email for gated access.
allowed-tools: ["Bash", "Read"]
argument-hint: <project name or page name>
---

# Publish — Live Interactive Shared Pages

Publish a project page to Cloudflare as a living document. Clients get a unique URL where they can check off tasks, leave section notes, post comments, and suggest new tasks. All changes sync back to your local database.

## Step 0: Check Setup

Check if Cloudflare is configured:

```sql
SELECT value FROM soy_meta WHERE key = 'cf_pages_project';
```

**If not configured**, run the one-time setup flow:

1. Check that `node` and `npx` are available:
   ```bash
   node --version && npx --version
   ```
   If missing, tell the user: "You'll need Node.js installed. Grab it from https://nodejs.org"

2. Ask the user to create a free Cloudflare account at https://dash.cloudflare.com if they don't have one.

3. Guide them to create an API token:
   - Go to https://dash.cloudflare.com/profile/api-tokens
   - Create a custom token with: **D1 Edit**, **Cloudflare Pages Edit**
   - Ask them to paste the token

4. Ask for their Cloudflare Account ID (visible on the dashboard right sidebar).

5. Store credentials:
   ```sql
   INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('cf_account_id', '<account_id>', datetime('now'));
   INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('cf_api_token', '<token>', datetime('now'));
   ```

6. Create D1 database:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/cloudflare" && npx wrangler d1 create soy-shared 2>&1
   ```
   Parse the database_id from the output and store it:
   ```sql
   INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('cf_d1_database_id', '<database_id>', datetime('now'));
   ```

7. Update wrangler.toml with the real database_id, then initialize the D1 schema:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/cloudflare" && npx wrangler d1 execute soy-shared --file=schema.sql --remote
   ```

8. Create and deploy the Pages project:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/cloudflare" && npm install && npx wrangler pages project create soy-shared --production-branch=main 2>&1
   ```
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/cloudflare" && npx wrangler pages deploy ./dist --project-name=soy-shared 2>&1
   ```

9. Store the project name:
   ```sql
   INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('cf_pages_project', 'soy-shared', datetime('now'));
   ```

10. Confirm: "Cloudflare is set up. Your shared pages will be at `https://soy-shared.pages.dev/p/...`"

Then continue to Step 1.

## Step 1: Resolve the Page

Match `$ARGUMENTS` against the `generated_views` table. Prefer project_page view types:

```sql
SELECT gv.id, gv.view_type, gv.entity_type, gv.entity_name, gv.filename,
       p.id as project_id, p.name as project_name
FROM generated_views gv
LEFT JOIN projects p ON gv.entity_type = 'project' AND gv.entity_id = p.id
WHERE gv.entity_name LIKE '%$ARGUMENTS%'
   OR gv.filename LIKE '%$ARGUMENTS%'
   OR gv.view_type LIKE '%$ARGUMENTS%'
ORDER BY gv.updated_at DESC;
```

**If no match:** Show available pages and ask the user which one to publish.

**If the matched page is not a project page**, resolve the project_id:
```sql
SELECT id, name FROM projects WHERE name LIKE '%$ARGUMENTS%' ORDER BY updated_at DESC LIMIT 1;
```

**Must have a project_id** — shared pages are tied to projects for task sync.

## Step 2: Get User Name

```sql
SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name';
```

## Step 3: Export the Clean HTML

Run the export script first to get a client-safe version:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/export_page.py" \
  "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/<filename>" \
  --user-name "<user_name>"
```

The script outputs JSON with `input`, `output`, `title`, and `size_kb`.

## Step 4: Publish to Cloudflare

Check if this project already has a published page (to reuse the token/URL):

```sql
SELECT token FROM shared_pages WHERE project_id = <project_id> AND status = 'active' ORDER BY id DESC LIMIT 1;
```

Run the publish script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/publish_page.py" publish \
  "<exported_html_path>" \
  --project-id <project_id> \
  --title "<title>" \
  [--token <existing_token>] \
  [--email <recipient_email>]
```

The script outputs JSON with `url`, `token`, `title`, `tasks_pushed`, and optionally `shared_with`.

### Resolving the email

If the user said to share with a person (not an email address), resolve the contact's email:

```sql
SELECT email FROM contacts WHERE name LIKE '%<name>%' AND email IS NOT NULL LIMIT 1;
```

If no email found, ask the user for the email address directly.

## Step 5: Send Invitation Email (if --email was used)

If `shared_with` is present in the publish output, send an invitation email via Gmail API.

1. Get the access token:
   ```bash
   ACCESS_TOKEN=$(python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/google_auth.py" token 2>/dev/null)
   ```

2. Get the user's own email:
   ```sql
   SELECT value FROM soy_meta WHERE key = 'google_email';
   ```

3. Compose and send a clean HTML email:

   **Subject:** `<user_name> shared "<project_name>" with you`

   **Body** (HTML email — clean, minimal design):
   - Brief intro: "\<user_name\> shared a project page with you."
   - The project title
   - A prominent "View Project" button linking to the published URL
   - Footer: "This page was shared with you privately. Enter your email when prompted to access it."

4. Send via Gmail API:
   ```bash
   python3 -c "
   import base64, json, urllib.request
   raw_email = 'From: <user_email>\r\nTo: <recipient_email>\r\nSubject: <subject>\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<html_body>'
   encoded = base64.urlsafe_b64encode(raw_email.encode()).decode()
   body = json.dumps({'raw': encoded}).encode()
   req = urllib.request.Request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
       data=body, headers={'Authorization': 'Bearer <access_token>', 'Content-Type': 'application/json'}, method='POST')
   resp = urllib.request.urlopen(req)
   print(json.loads(resp.read()))
   "
   ```

5. Record that the invitation was sent:
   ```sql
   UPDATE shared_page_access SET invitation_sent_at = datetime('now')
   WHERE shared_page_id = (SELECT id FROM shared_pages WHERE token = '<token>')
     AND email = '<recipient_email>';
   ```

## Step 6: Log Activity

```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('project', <project_id>, 'page_published',
        'Published live page: <url>', datetime('now'));
```

## Step 7: Confirm

Tell the user:

> **Published!** Your live project page is at:
> **<url>**
>
> Your client can:
> - Check off tasks as they complete them
> - Leave notes on any section
> - Post comments in the thread
> - Suggest new tasks (you'll review them before they hit the backlog)
>
> The page updates every time you re-publish. Client changes sync back automatically.

**If email-gated access was set**, also mention:

> Access is restricted to **<email>**. I sent them an invitation — they'll enter their email to unlock the page. The session lasts 90 days.

**If no email was specified**, ask:

> Want to restrict access to a specific email? Just say "share with <email>" and I'll lock it down + send an invite.

If this is the first publish, also mention:
> Tip: Run `/publish <project>` again anytime to update the page with latest data. The URL stays the same.
