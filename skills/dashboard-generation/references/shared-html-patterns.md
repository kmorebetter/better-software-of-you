# Shared HTML Patterns

Reusable HTML/Tailwind snippets that appear across multiple view-generating commands. When building any view, use these patterns verbatim rather than re-specifying from scratch. All patterns assume Tailwind CDN, Lucide CDN, and Inter font are loaded (provided by `template-base.html`).

---

## 1. Page Header Card

Used by: dashboard, journal-view, timeline, weekly-review, nudges-view, search-hub

The full-width header card at the top of every page. Always includes: icon + title, subtitle/description, and optional stat pills on the right.

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 mb-6">
  <div class="flex items-center justify-between flex-wrap gap-3">
    <div>
      <div class="flex items-center gap-2">
        <i data-lucide="ICON" class="w-5 h-5 text-zinc-700"></i>
        <h1 class="text-2xl font-bold text-zinc-900">Page Title</h1>
      </div>
      <p class="text-sm text-zinc-500 mt-1">Subtitle or context line</p>
    </div>
    <div class="flex items-center gap-2 flex-wrap">
      <!-- Stat pills — see Stat Pills pattern below -->
    </div>
  </div>
</div>
```

When the page has no meaningful subtitle, omit the `<p>` tag rather than leaving it empty.

---

## 2. Stat Pills (Header Badges)

Used by: dashboard, journal-view, weekly-review, nudges-view, entity-page

Colored pill badges rendered in the header card's right side, or inline anywhere. Each pill represents a count or category label.

```html
<!-- Blue — contacts, meetings, general counts -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">X items</span>

<!-- Amber — warnings, pending, energy averages -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">Pending</span>

<!-- Emerald — done, positive, streaks -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">X done</span>

<!-- Red — urgent, overdue -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700">X Urgent</span>

<!-- Indigo — email -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">X emails</span>

<!-- Purple — projects, tasks -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-700">X tasks done</span>

<!-- Rose — journal -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700">X entries</span>

<!-- Zinc — neutral, streaks, misc -->
<span class="px-3 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">Z day streak</span>
```

Only render pills for data that exists. Omit pills with a zero value unless the zero is meaningful (e.g., "0 urgent" in a nudges header).

---

## 3. Section Card

Used by: all views

The standard white card wrapper for every section. Use `p-5` for tighter sidebar-column cards, `p-6` for main content cards.

```html
<!-- Standard section card -->
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
  <div class="flex items-center gap-2 mb-4">
    <i data-lucide="ICON" class="w-4 h-4 text-zinc-400"></i>
    <h3 class="text-sm font-semibold text-zinc-700">Section Title</h3>
    <span class="text-xs text-zinc-400 ml-auto">Optional count or context</span>
  </div>
  <!-- Section content -->
</div>
```

The `ml-auto` on the trailing span pushes it to the right without flexbox gymnastics. Add `delight-card` to cards that should animate in on page load.

---

## 4. Section Divider Header

Used by: journal-view, timeline, weekly-review

A labeled horizontal rule that groups content into named buckets ("This Week", "Today", "Looking Ahead").

```html
<div class="flex items-center gap-3 mt-6 mb-4">
  <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider whitespace-nowrap">Section Label</h3>
  <div class="flex-1 h-px bg-zinc-200"></div>
  <!-- Optional trailing label -->
  <span class="text-xs text-zinc-300">Feb 19</span>
</div>
```

The trailing label is optional — use it for date context on timeline buckets. Omit it for column headers like "This Week" / "Looking Ahead".

---

## 5. Filter/Category Tabs

Used by: timeline, search-hub

Pill-shaped filter buttons for client-side JS filtering. The active tab has a dark filled background.

```html
<div class="flex items-center gap-1 flex-wrap">
  <button class="filter-tab active" data-filter="all">All</button>
  <button class="filter-tab" data-filter="contacts">Contacts</button>
  <button class="filter-tab" data-filter="email">Email</button>
  <!-- Add tabs only for installed modules -->
</div>
```

```css
.filter-tab {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  color: #71717a;
  background: transparent;
  border: 1px solid #e4e4e7;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-tab:hover {
  background: #f4f4f5;
  color: #18181b;
}
.filter-tab.active {
  background: #18181b;
  color: white;
  border-color: #18181b;
}
```

The same CSS applies when the class is named `.search-filter` (search-hub) or `.filter-tab` (timeline) — use whichever name matches the JavaScript that operates it.

---

## 6. Left-Border Accent Cards (Urgency/Status Rows)

Used by: nudges-view, dashboard, weekly-review, timeline

Cards or rows with a colored 4px left border to signal urgency or category at a glance. The border color is the primary visual signal.

```html
<!-- Urgent / Overdue (red) -->
<div class="bg-white rounded-lg border border-zinc-200 p-4 mb-2 border-l-4 border-l-red-400">
  <div class="flex items-start gap-3">
    <i data-lucide="clock" class="w-4 h-4 text-red-500 mt-0.5 shrink-0"></i>
    <div>
      <div class="text-sm font-medium text-zinc-900">Item title or linked name</div>
      <p class="text-xs text-zinc-500 mt-1">Context line</p>
      <p class="text-xs text-zinc-400 mt-1">Suggested action</p>
    </div>
  </div>
</div>

<!-- Soon / Warning (amber) -->
<div class="bg-white rounded-lg border border-zinc-200 p-4 mb-2 border-l-4 border-l-amber-400">
  <!-- same inner structure, icon uses text-amber-500 -->
</div>

<!-- Awareness / Info (blue) -->
<div class="bg-white rounded-lg border border-zinc-200 p-4 mb-2 border-l-4 border-l-blue-400">
  <!-- same inner structure, icon uses text-blue-500 -->
</div>

<!-- Calendar / Green (upcoming events, next steps) -->
<div class="bg-amber-50 border border-amber-100 rounded-lg p-4 border-l-4 border-l-amber-400">
  <!-- "Next up" highlighted event row — amber background, not white -->
</div>
```

Icon color always matches the border accent color. Use `shrink-0` on the icon to prevent it from collapsing.

---

## 7. Icon + Label Row (Section Header Inside Card)

Used by: journal-view, weekly-review, nudges-view, entity-page, search-hub

A consistent pattern for labeling a result group, data section, or module block inside a card.

```html
<div class="flex items-center gap-2 mb-3">
  <i data-lucide="users" class="w-4 h-4 text-blue-500"></i>
  <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Contacts</h3>
  <span class="text-xs text-zinc-400">(3 matches)</span>
</div>
```

The count/context span after the label is optional. When used inside the result group headers of search-hub, include the match count. When used for module sections in weekly-review, omit it or use the right-aligned `ml-auto` pattern from Section Card above.

---

## 8. Entity/Contact Pill Links

Used by: journal-view, entity-page, timeline, weekly-review, search-hub

Small inline pills for linking to contacts or projects. Linked version uses blue styling; static (no page exists) version uses zinc.

```html
<!-- Linked contact pill (entity page exists) -->
<a href="contact-sarah-chen.html" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors">
  <i data-lucide="user" class="w-3 h-3"></i>
  Sarah Chen
</a>

<!-- Static contact pill (no entity page) -->
<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-zinc-100 text-zinc-600">
  <i data-lucide="user" class="w-3 h-3"></i>
  Sarah Chen
</span>

<!-- Linked project pill -->
<a href="project-meridian.html" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-zinc-100 text-zinc-600 hover:bg-zinc-200 transition-colors">
  <i data-lucide="folder" class="w-3 h-3"></i>
  Meridian Rebrand
</a>
```

Always check `generated_views` before rendering a pill as a link. If no page exists, use the static `<span>` version. Use `w-3 h-3` icons inside pills (not `w-4 h-4`).

---

## 9. Contact Name Inline Link

Used by: all views

Anywhere a contact name appears in body text (not as a pill, but as a hyperlink inline with prose), use this pattern:

```html
<!-- Linked (entity page exists) -->
<a href="contact-sarah-chen.html" class="font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>

<!-- Static (no entity page) -->
<span class="font-medium text-zinc-900">Sarah Chen</span>
```

Check `generated_views` before rendering as a link. Never render a link with a `#` or placeholder href — if no page exists, use the static span.

---

## 10. Contact Avatar (Initials Circle)

Used by: dashboard, timeline, search-hub, entity-page

A colored circle with the contact's initials. Generate initials from the first letter of each word in the name (max 2 characters).

```html
<!-- Standard contact avatar -->
<div class="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-sm font-semibold shrink-0">SC</div>

<!-- Small (in result cards, email rows) -->
<div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-semibold shrink-0">SC</div>

<!-- "You" (outbound sender in email threads) -->
<div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 text-xs font-semibold shrink-0">Me</div>

<!-- Third party / unknown -->
<div class="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-500 text-xs font-semibold shrink-0">??</div>
```

Use `shrink-0` to prevent the avatar from collapsing in flex layouts.

---

## 11. Module/Category Icon Badges (Square)

Used by: timeline, search-hub

Square icon containers used for non-contact entity types (emails, projects, decisions, etc.).

```html
<!-- Email -->
<div class="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
  <i data-lucide="mail" class="w-4 h-4 text-indigo-500"></i>
</div>

<!-- Project -->
<div class="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center shrink-0">
  <i data-lucide="folder" class="w-4 h-4 text-purple-500"></i>
</div>

<!-- Decision -->
<div class="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center shrink-0">
  <i data-lucide="git-branch" class="w-4 h-4 text-amber-500"></i>
</div>

<!-- Journal -->
<div class="w-8 h-8 rounded-lg bg-rose-50 flex items-center justify-center shrink-0">
  <i data-lucide="book-open" class="w-4 h-4 text-rose-500"></i>
</div>

<!-- Commitment -->
<div class="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center shrink-0">
  <i data-lucide="target" class="w-4 h-4 text-teal-500"></i>
</div>

<!-- Transcript / Call -->
<div class="w-8 h-8 rounded-lg bg-cyan-50 flex items-center justify-center shrink-0">
  <i data-lucide="message-square" class="w-4 h-4 text-cyan-500"></i>
</div>
```

Larger (w-9/h-9) for Intelligence Tools strip cards. Smaller (w-7/h-7) for inline result cards. Always `rounded-lg` for square icons, `rounded-full` for contact avatars.

---

## 12. Module Color + Icon Reference

Used by: all views

Single source of truth for color/icon assignment per module and entity type.

| Entity / Module | Icon | Color | Background | Text |
|----------------|------|-------|------------|------|
| Contact / CRM | `users` | blue | `bg-blue-50` | `text-blue-500` |
| Email / Gmail | `mail` | indigo | `bg-indigo-50` | `text-indigo-500` |
| Calendar event | `calendar` | green | `bg-green-50` | `text-green-500` |
| Project | `folder` | purple | `bg-purple-50` | `text-purple-500` |
| Task | `check-square` | purple | `bg-purple-50` | `text-purple-500` |
| Decision | `git-branch` | amber | `bg-amber-50` | `text-amber-500` |
| Journal | `book-open` | rose | `bg-rose-50` | `text-rose-500` |
| Commitment | `target` | teal | `bg-teal-50` | `text-teal-500` |
| Transcript / Call | `message-square` | cyan | `bg-cyan-50` | `text-cyan-500` |
| Follow-up | `clock` | amber | `bg-amber-50` | `text-amber-500` |
| Note | `sticky-note` | violet | `bg-violet-50` | `text-violet-500` |

Border accent colors for left-border cards follow the same column mapping: blue-400, indigo-400, green-400, purple-400, amber-400, rose-400, teal-400, cyan-400.

---

## 13. Empty State — Standard

Used by: all views

A centered empty state shown when a section has no data. Use the `delight-patterns.md` copy table for specific wording. The icon should match the section's entity type.

```html
<div class="text-center py-12">
  <div class="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mx-auto mb-3">
    <i data-lucide="ICON" class="w-6 h-6 text-zinc-400"></i>
  </div>
  <p class="text-sm text-zinc-500 font-medium">Nothing here yet</p>
  <p class="text-xs text-zinc-400 mt-1">Context-specific guidance line</p>
</div>
```

Never hide a section because it has no data when the module is installed. Show the empty state instead — it tells the user the feature is available.

---

## 14. Empty State — All Clear (Celebration)

Used by: nudges-view, dashboard follow-ups section

When the empty state is a positive outcome (no overdue items, no urgent nudges), use the green celebration variant.

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-12 text-center">
  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-50 mb-4">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
         stroke-linecap="round" stroke-linejoin="round" class="text-emerald-600 delight-check">
      <polyline points="4 12 9 17 20 7"></polyline>
    </svg>
  </div>
  <h3 class="text-lg font-semibold text-zinc-900 mb-1">Nothing needs your attention</h3>
  <p class="text-sm text-zinc-500">All clear — nice work.</p>
</div>
```

The `delight-check` class on the `<polyline>` draws the checkmark with an SVG stroke animation. This requires the delight JS from `template-base.html`.

---

## 15. Empty State — Large (Full Page)

Used by: timeline, nudges-view (when zero data exists)

When an entire page has no data at all (not just an empty section), use the larger centered empty state.

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-12 text-center">
  <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-50 mb-4">
    <i data-lucide="ICON" class="w-8 h-8 text-zinc-300"></i>
  </div>
  <h3 class="text-lg font-semibold text-zinc-900 mb-1">No activity yet</h3>
  <p class="text-sm text-zinc-500">Your data will appear here as you use the platform.</p>
</div>
```

Use `w-8 h-8 text-zinc-300` for the icon — lighter than the section empty state, because this is a true zero state, not a filtered empty.

---

## 16. Inline Empty State (Within a Card)

Used by: weekly-review, journal-view, dashboard

When a section card has data for some items but not others, or the module is installed but has no data this period, show a minimal inline message rather than a full centered block.

```html
<p class="text-sm text-zinc-400 italic">No meetings this week.</p>
```

Or with a `coffee` icon for a quiet week:

```html
<div class="flex items-center gap-2 py-4 text-zinc-400">
  <i data-lucide="coffee" class="w-4 h-4"></i>
  <span class="text-sm italic">Quiet week — no recorded activity.</span>
</div>
```

---

## 17. View Registration SQL

Used by: all view-generating commands

Every generated page must be registered in `generated_views` so other pages can link to it. The `ON CONFLICT` clause makes this idempotent — safe to run on every regeneration.

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('module_view', 'module', NULL, 'View Name', 'filename.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

For entity pages (contact or project pages):

```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('entity_page', 'contact', ?, 'Contact Name', 'contact-slug.html')
ON CONFLICT(filename) DO UPDATE SET
  entity_name = excluded.entity_name,
  updated_at = datetime('now');
```

---

## 18. Standard Nav Badge Data Query

Used by: timeline, weekly-review, nudges-view, search-hub

A UNION query that fetches counts for the sidebar's badge indicators. Run this in the same heredoc as other data queries.

```sql
SELECT 'contacts' as section, COUNT(*) as count FROM contacts WHERE status = 'active'
UNION ALL SELECT 'emails', COUNT(*) FROM emails
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar_events WHERE start_time > datetime('now', '-30 days')
UNION ALL SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'journal', COUNT(*) FROM journal_entries;
```

Only query tables for installed modules — if a module isn't installed, its table may not exist. Wrap UNION branches in a module-installed check when needed.

---

## 19. Footer

Used by: all views

Every generated page ends with a minimal footer.

```html
<footer class="mt-8 pt-4 border-t border-zinc-100 text-center">
  <p class="text-xs text-zinc-400">Generated by Software of You · DATE at TIME</p>
</footer>
```

Replace `DATE at TIME` with the actual generation timestamp (e.g., "March 4, 2026 at 2:15 PM").

---

## 20. Intelligence Tools Strip (Dashboard Only)

Used by: dashboard

A 4-card grid linking to the platform's cross-cutting views. Placed after the header and before content sections. Always included on the dashboard.

```html
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
  <a href="weekly-review.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-blue-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
        <i data-lucide="clipboard-list" class="w-4 h-4 text-blue-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-blue-700">Weekly Review</div>
        <div class="text-xs text-zinc-500">Your week at a glance</div>
      </div>
    </div>
  </a>

  <a href="nudges.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-amber-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center relative">
        <i data-lucide="bell" class="w-4 h-4 text-amber-600"></i>
        <!-- Only include this span if urgent_count > 0 -->
        <span class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold">N</span>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-amber-700">Nudges</div>
        <div class="text-xs text-zinc-500">Items need attention</div>
      </div>
    </div>
  </a>

  <a href="timeline.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-purple-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center">
        <i data-lucide="clock" class="w-4 h-4 text-purple-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-purple-700">Timeline</div>
        <div class="text-xs text-zinc-500">Activity across everything</div>
      </div>
    </div>
  </a>

  <a href="search.html" class="bg-white rounded-xl border border-zinc-200 p-4 hover:border-emerald-300 hover:shadow-sm transition-all group">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
        <i data-lucide="search" class="w-4 h-4 text-emerald-600"></i>
      </div>
      <div>
        <div class="text-sm font-semibold text-zinc-900 group-hover:text-emerald-700">Search</div>
        <div class="text-xs text-zinc-500">Find anything</div>
      </div>
    </div>
  </a>
</div>
```

Replace `N` in the Nudges badge with the actual urgent count from the nudge query. Omit the badge `<span>` entirely when `urgent_count = 0`.

---

## 21. Callout / Informational Banner

Used by: dashboard (Google not connected), nudges-view (hero callout), entity-page

Two variants: amber for urgency/action-required, blue for informational/setup prompts.

```html
<!-- Amber — action required -->
<div class="bg-amber-50 border border-amber-100 rounded-xl p-4 border-l-4 border-l-amber-400">
  <div class="flex items-start gap-3">
    <i data-lucide="alert-triangle" class="w-5 h-5 text-amber-500 shrink-0 mt-0.5"></i>
    <div>
      <p class="text-sm font-medium text-amber-900">Action required headline</p>
      <p class="text-xs text-amber-700 mt-1">Supporting context or description.</p>
    </div>
  </div>
</div>

<!-- Blue — informational / setup prompt -->
<div class="bg-blue-50 border border-blue-100 rounded-xl p-4">
  <div class="flex items-start gap-3">
    <i data-lucide="info" class="w-5 h-5 text-blue-400 shrink-0 mt-0.5"></i>
    <div>
      <p class="text-sm font-medium text-blue-900">Informational headline</p>
      <p class="text-xs text-blue-700 mt-1">Supporting context. Run <code>/command</code> to get started.</p>
    </div>
  </div>
</div>
```

---

## 22. Mention/Reference List (Sidebar Card)

Used by: journal-view, weekly-review

A compact list inside a sidebar card showing contacts or projects with a count, linking to entity pages where available.

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5 mb-4">
  <div class="flex items-center gap-2 mb-4">
    <i data-lucide="users" class="w-4 h-4 text-zinc-400"></i>
    <h3 class="text-sm font-semibold text-zinc-700">Card Title</h3>
  </div>
  <div class="space-y-2.5">
    <div class="flex items-center justify-between">
      <!-- Linked name if entity page exists -->
      <a href="contact-sarah-chen.html" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Sarah Chen</a>
      <span class="text-xs text-zinc-400">5 mentions</span>
    </div>
    <div class="flex items-center justify-between">
      <!-- Static name if no entity page -->
      <span class="text-sm font-medium text-zinc-900">Daniel Byrne</span>
      <span class="text-xs text-zinc-400">2 mentions</span>
    </div>
  </div>
</div>
```

Empty state for this card:
```html
<p class="text-xs text-zinc-400">No mentions recently.</p>
```

---

## Design Constants (Non-Negotiable)

These values are invariant across all views. Never deviate from them.

| Property | Value |
|----------|-------|
| Page background | `bg-zinc-50` |
| Card background | `bg-white` |
| Card border | `border border-zinc-200` |
| Card rounding | `rounded-xl` |
| Card shadow | `shadow-sm` |
| Card padding (main) | `p-6` |
| Card padding (sidebar/compact) | `p-5` |
| Body text | `text-zinc-900` |
| Secondary text | `text-zinc-500` |
| Tertiary text | `text-zinc-400` |
| Link color | `text-blue-600 hover:text-blue-800` |
| Section heading style | `text-xs font-semibold text-zinc-400 uppercase tracking-wider` |
| JS data loading | None — all data is static in HTML |
| JS allowed | Lucide icon init + delight layer from template-base.html |
| Responsive column grid | `grid grid-cols-1 lg:grid-cols-2 gap-6` |
