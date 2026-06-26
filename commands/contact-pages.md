---
description: Rebuild every contact's intelligence sheet (the "Your People" pages) from the database
allowed-tools: ["Bash"]
---

# Contact Pages

Rebuild the deterministic contact sheets — one HTML page per contact plus the **Your People** index — directly from the database. Use this after enriching contacts, importing a call, or any time the sheets may be stale.

This is the **batch renderer** (fast, consistent, all contacts at once). For a single deep, bespoke brief on one person, use `/entity-page <name>` instead.

## Run

1. Bootstrap (idempotent):
   ```
   bash "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/shared/bootstrap.sh"
   ```
2. Build all sheets:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/scripts/build_contact_pages.py"
   ```
3. Open the index for the user:
   ```
   open "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/contact-cards.html"
   ```

The builder reads only — it never modifies data. It surfaces real values from `relationship_scores`, `v_contact_health`, `conversation_metrics`, `communication_insights`, `contact_interactions`, `commitments`, `emails`, and the contact's interaction-derived `notes`. Gaps render as "—", never invented. Output: `output/people/<slug>.html` + `output/contact-cards.html`.

## When this runs automatically

- After `/import-call` analyzes a new transcript (the participants' sheets refresh).
- As part of the scheduled background sync (`shared/scheduled_sync.sh`), so sheets stay current hands-off.
- Whenever contacts are enriched from interactions — see CLAUDE.md → "Enrich contacts from interactions".
