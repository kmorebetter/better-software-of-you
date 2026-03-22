---
description: Review and route unrouted inbox items
allowed-tools: ["Bash", "Read", "Write"]
---

# Inbox Review

Review unrouted inbox items and help the user route them to the right modules.

## Workflow

1. Query unrouted items:
   ```sql
   SELECT id, content, tags, matched_contacts, created_at
   FROM inbox
   WHERE routed_to IS NULL
   ORDER BY created_at DESC
   LIMIT 30;
   ```

2. If no items: "Your inbox is clear — nothing to route." and stop.

3. Present items as a numbered list:
   ```
   1. "met Jake at coffee, interested in the API project" — 2 days ago
      → Matched: Jake Smith | Suggested: route to Jake's contact record
   2. "need to decide on #pricing for the new tier" — 1 day ago
      → Tags: #pricing | Suggested: route to decision log
   3. "feeling overwhelmed with Q2 planning" — 3 hours ago
      → Suggested: route to journal
   ```

4. For each item, suggest a routing destination based on:
   - Has matched contacts → route to contact record as a note
   - Starts with "Decision:" or describes a choice → decision log
   - Reflective/emotional → journal
   - Task or deliverable → project (ask which one)
   - No clear destination → "Leave as-is for now"

5. Ask user what to do: "Route, dismiss, or skip each item?"

6. For routing, UPDATE the inbox item:
   ```sql
   UPDATE inbox SET routed_to = '<type>', routed_entity_id = <id>,
     routed_at = datetime('now'), updated_at = datetime('now')
   WHERE id = <inbox_id>;
   INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
   VALUES ('inbox', <inbox_id>, 'routed', 'Routed to <type> #<entity_id>', datetime('now'));
   ```

7. For dismissing:
   ```sql
   UPDATE inbox SET routed_to = 'dismissed', routed_at = datetime('now'),
     updated_at = datetime('now')
   WHERE id = <inbox_id>;
   INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
   VALUES ('inbox', <inbox_id>, 'dismissed', 'Inbox item dismissed', datetime('now'));
   ```

8. Batch mode: If 3+ items have the same obvious destination (e.g., all mention contacts), offer: "Route all 3 people-mentions to their contact notes?"
