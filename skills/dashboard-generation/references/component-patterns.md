# Component Patterns

Reusable HTML snippets for dashboard views. Use Tailwind classes exactly as shown for visual consistency.

**Delight classes:** All components below include delight classes from `delight-patterns.md`. These are built into `template-base.html` and work automatically — no extra CSS/JS needed.

## Stat Card (small)

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-4 delight-card">
    <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
            <i data-lucide="users" class="w-5 h-5 text-blue-600"></i>
        </div>
        <div>
            <p class="text-2xl font-bold" data-countup="24">24</p>
            <p class="text-sm text-zinc-500">Contacts</p>
        </div>
    </div>
</div>
```

`data-countup` animates the number from 0. The inner text is the no-JS fallback. For suffixes: `data-countup-suffix="%"`.

## Section Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 delight-card">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="folder" class="w-5 h-5 text-zinc-400"></i>
        <h2 class="text-lg font-semibold">Section Title</h2>
    </div>
    <!-- Content here -->
</div>
```

Add `delight-hover` if the card links somewhere.

## Data Table

```html
<table class="w-full text-sm">
    <thead>
        <tr class="border-b border-zinc-100">
            <th class="text-left py-2 text-zinc-500 font-medium">Name</th>
            <th class="text-left py-2 text-zinc-500 font-medium">Status</th>
            <th class="text-right py-2 text-zinc-500 font-medium">Date</th>
        </tr>
    </thead>
    <tbody>
        <tr class="border-b border-zinc-50 delight-row">
            <td class="py-2.5 font-medium"><a href="contact-item.html" class="text-blue-600 delight-link">Item Name</a></td>
            <td class="py-2.5"><span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">Active</span></td>
            <td class="py-2.5 text-right text-zinc-500">Feb 18, 2026</td>
        </tr>
    </tbody>
</table>
```

Use `delight-row` instead of `hover:bg-zinc-50` — it provides a smooth transition. Use `delight-link` on contact/project name links.

## Status Badge

```html
<!-- Active/Good -->
<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">Active</span>

<!-- Warning/Pending -->
<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700">Pending</span>

<!-- Urgent/Overdue -->
<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700">Overdue</span>

<!-- Neutral/Paused -->
<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">Paused</span>

<!-- Info/Planning -->
<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">Planning</span>
```

## Priority Indicator

```html
<!-- Urgent -->
<span class="text-red-600 font-medium">Urgent</span>
<!-- High -->
<span class="text-amber-600 font-medium">High</span>
<!-- Medium -->
<span class="text-zinc-600">Medium</span>
<!-- Low -->
<span class="text-zinc-400">Low</span>
```

## Timeline Entry

```html
<div class="flex gap-3 py-2.5 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="plus" class="w-4 h-4 text-blue-600"></i>
    </div>
    <div>
        <p class="text-sm"><span class="font-medium">Created contact</span> "Jane Doe"</p>
        <p class="text-xs text-zinc-400 mt-0.5">2 hours ago</p>
    </div>
</div>
```

## Empty State

Use warm, encouraging copy that matches the brand voice. See `delight-patterns.md` for the full empty state copy table.

```html
<div class="text-center py-12">
    <div class="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mx-auto">
        <i data-lucide="coffee" class="w-6 h-6 text-zinc-400"></i>
    </div>
    <p class="text-sm text-zinc-600 mt-3 font-medium">Your network starts here</p>
    <p class="text-xs text-zinc-400 mt-1">Add someone you work with — I'll start tracking from there</p>
</div>
```

## Empty State — All Clear (for sections that normally have items)

When nudges, overdue commitments, or pending follow-ups are empty, celebrate it:

```html
<div class="text-center py-12">
    <div class="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mx-auto">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-green-600">
            <polyline points="4 12 9 17 20 7" class="delight-check"></polyline>
        </svg>
    </div>
    <p class="text-sm text-zinc-600 mt-3 font-medium">Nothing needs your attention</p>
    <p class="text-xs text-zinc-400 mt-1">All clear — nice work</p>
</div>
```

## Progress Bar

```html
<div class="w-full bg-zinc-100 rounded-full h-2">
    <div class="bg-blue-600 h-2 rounded-full delight-progress" style="width: 65%"></div>
</div>
```

`delight-progress` animates the bar from 0% to the set width on page load.

## Lucide Icon Names (commonly used)

- Contacts: `users`, `user`, `user-plus`
- Projects: `folder`, `folder-open`, `briefcase`
- Tasks: `check-square`, `square`, `circle-check`
- Calendar: `calendar`, `clock`
- Activity: `activity`, `zap`
- Notes: `file-text`, `sticky-note`
- Tags: `tag`, `tags`
- Search: `search`
- Settings: `settings`
- Alert: `alert-circle`, `alert-triangle`
- Positive: `trending-up`, `check-circle`
- Communication: `mail`, `phone`, `message-circle`
