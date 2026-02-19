# Component Patterns

Reusable HTML snippets for dashboard views. Use Tailwind classes exactly as shown for visual consistency.

## Stat Card (small)

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-4">
    <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
            <i data-lucide="users" class="w-5 h-5 text-blue-600"></i>
        </div>
        <div>
            <p class="text-2xl font-bold">24</p>
            <p class="text-sm text-zinc-500">Contacts</p>
        </div>
    </div>
</div>
```

## Section Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="folder" class="w-5 h-5 text-zinc-400"></i>
        <h2 class="text-lg font-semibold">Section Title</h2>
    </div>
    <!-- Content here -->
</div>
```

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
        <tr class="border-b border-zinc-50 hover:bg-zinc-50">
            <td class="py-2.5 font-medium">Item Name</td>
            <td class="py-2.5"><span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">Active</span></td>
            <td class="py-2.5 text-right text-zinc-500">Feb 18, 2026</td>
        </tr>
    </tbody>
</table>
```

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

```html
<div class="text-center py-8">
    <i data-lucide="inbox" class="w-10 h-10 text-zinc-300 mx-auto"></i>
    <p class="text-sm text-zinc-400 mt-2">No items yet</p>
    <p class="text-xs text-zinc-400 mt-1">Use /contact to add your first contact</p>
</div>
```

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
