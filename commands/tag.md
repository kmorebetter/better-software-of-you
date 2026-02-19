---
description: Manage tags — create, list, or apply tags to entities
allowed-tools: ["Bash"]
argument-hint: <action> [tag name] [entity name] or "list"
---

# Tag Management

Handle tag operations based on $ARGUMENTS. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Operations

**List all tags** (argument is "list" or empty):
```sql
SELECT t.name, t.color, t.category, COUNT(et.tag_id) as usage_count
FROM tags t LEFT JOIN entity_tags et ON et.tag_id = t.id
GROUP BY t.id ORDER BY usage_count DESC;
```

**Create a tag** (e.g., "create VIP" or "new tag Important --color #ef4444"):
```sql
INSERT INTO tags (name, color, category) VALUES (?, ?, ?);
```

**Apply a tag to an entity** (e.g., "tag John Smith as VIP"):
1. Find the contact/project by name
2. Find or create the tag by name
3. Link them:
```sql
INSERT OR IGNORE INTO entity_tags (entity_type, entity_id, tag_id) VALUES (?, ?, ?);
```
4. Log the activity

**Remove a tag from an entity** (e.g., "untag John Smith from VIP"):
```sql
DELETE FROM entity_tags WHERE entity_type = ? AND entity_id = ? AND tag_id = ?;
```

Confirm each operation clearly.
