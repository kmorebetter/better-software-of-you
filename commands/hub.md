---
description: Launch the SoY hub — your home base for all views
allowed-tools: ["Bash", "Read", "Write"]
---

# SoY Hub — Home Base

Launch the unified SoY server and open the hub in your browser. The hub shows all your generated views (dashboards, prep docs, entity pages) plus quick links to tools like the audition board.

## Step 1: Open the Hub

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/open_page.sh"
```

This auto-starts the server if needed and opens the hub (no filename argument = hub).

## Step 2: Confirm

Tell the user:

"SoY Hub is live at **http://localhost:8787**

- **Home** — all your generated pages in one place
- **Audition Board** — at `/auditions`
- **Prep docs, dashboards, entity pages** — all accessible via sidebar or hub cards

The server runs in the background. It'll stop when you close this session, or you can stop it with `pkill -f soy_server`."
