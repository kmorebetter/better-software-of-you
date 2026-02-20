# Navigation Patterns

Shared navigation components for all generated HTML views. Every page in Software of You includes a nav bar for moving between views.

## How Navigation Works

Before generating any HTML page, query `generated_views` for recent pages:

```sql
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC
LIMIT 15;
```

Use this to populate the nav bar with links to other existing pages.

## After Writing Any HTML Page

**Always register/update the view in the database:**

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

For dashboards: `view_type = 'dashboard'`, `entity_type = NULL`, `entity_id = NULL`, `entity_name = 'Dashboard'`, `filename = 'dashboard.html'`

For entity pages: `view_type = 'entity_page'`, `entity_type = 'contact'`, `entity_id = <id>`, `entity_name = <contact name>`, `filename = 'contact-{slug}.html'`

## Module View Registration

For module-specific views, use `view_type = 'module_view'`:

| View | entity_name | filename |
|------|-------------|----------|
| Email Hub | 'Email Hub' | 'email-hub.html' |
| Week View | 'Week View' | 'week-view.html' |
| Conversations | 'Conversations' | 'conversations.html' |
| Decision Journal | 'Decision Journal' | 'decision-journal.html' |
| Journal | 'Journal' | 'journal.html' |
| Network Map | 'Network Map' | 'network-map.html' |

## Nav Bar Component

Include at the top of every generated page, inside the `max-w-5xl` container, before any content.

```html
<nav class="flex items-center justify-between mb-6 pb-4 border-b border-zinc-200">
    <div class="flex items-center gap-3">
        <!-- Home link (always present) -->
        <a href="dashboard.html" class="flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition-colors">
            <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
            <span>Dashboard</span>
        </a>

        <!-- Separator + current page breadcrumb (on entity pages) -->
        <span class="text-zinc-300">/</span>
        <span class="text-sm font-medium text-zinc-900">Daniel Byrne</span>
    </div>

    <!-- Quick links to other generated pages -->
    <div class="flex items-center gap-2">
        <a href="contact-sarah-chen.html" class="px-2.5 py-1 rounded-full text-xs bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors">Sarah Chen</a>
        <a href="contact-vahid-jozi.html" class="px-2.5 py-1 rounded-full text-xs bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors">Vahid Jozi</a>
    </div>
</nav>
```

### Dashboard Nav (simpler — no breadcrumb)

```html
<nav class="flex items-center justify-between mb-6 pb-4 border-b border-zinc-200">
    <div class="flex items-center gap-1.5">
        <i data-lucide="layout-dashboard" class="w-4 h-4 text-zinc-900"></i>
        <span class="text-sm font-medium text-zinc-900">Dashboard</span>
    </div>

    <!-- Quick links to generated pages -->
    <div class="flex items-center gap-2">
        <!-- Module views (always show if generated) -->
        <a href="email-hub.html" class="px-2.5 py-1 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">Email Hub</a>
        <a href="week-view.html" class="px-2.5 py-1 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">Week View</a>

        <!-- Entity pages -->
        <a href="contact-daniel-byrne.html" class="px-2.5 py-1 rounded-full text-xs bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors">Daniel Byrne</a>
        <a href="contact-sarah-chen.html" class="px-2.5 py-1 rounded-full text-xs bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors">Sarah Chen</a>
    </div>
</nav>
```

### Rules

- Quick links show **only pages that exist** in `generated_views` — never link to a page that hasn't been generated
- Module view pills use `bg-blue-50 text-blue-600` to distinguish from entity page pills (`bg-zinc-100 text-zinc-600`)
- Module views show first in the nav bar, then entity pages
- Only show module views that exist in `generated_views`
- Limit: show all module views + up to 5 entity pages
- On entity pages, quick links show other entity pages (not the current one)
- Links use relative paths (all pages live in `output/` together)
- The current page is shown as plain text (not a link)

## Contact Name Links in Dashboard

When the dashboard displays contact names (in activity feeds, follow-ups, project cards, etc.), **check if an entity page exists** for that contact:

```sql
SELECT filename FROM generated_views WHERE entity_type = 'contact' AND entity_id = ?;
```

If a page exists, wrap the name in an `<a>` tag:
```html
<a href="contact-daniel-byrne.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Daniel Byrne</a>
```

If no page exists, render the name as plain text (not a link).

## Page Footer with Freshness

Every page includes a footer showing when it was generated:

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
    <p class="text-xs text-zinc-400">Generated by Software of You · February 19, 2026 at 3:45 PM</p>
</footer>
```
