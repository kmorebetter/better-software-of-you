---
name: dashboard-generation
description: Use when generating any HTML dashboard or view for Software of You. Provides the design system, base template, and component patterns for consistent visual output across all modules.
version: 1.0.0
---

# Dashboard & View Generation

Software of You generates self-contained HTML files on demand — no server, no build step. Every view is a single HTML file with inline styles via Tailwind CSS CDN.

## When to Use

- `/dashboard` — generate the unified home dashboard
- `/view <module>` — generate a module-specific view
- Any natural language request for a visual report or custom view

## Design System

All views share a consistent visual language:

- **CSS:** Tailwind CSS via CDN (`<script src="https://cdn.tailwindcss.com"></script>`)
- **Icons:** Lucide via CDN (`<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>`)
- **Font:** Inter from Google Fonts
- **Colors:** zinc/slate palette (zinc-50 background, zinc-900 text, blue-600 accents)
- **Layout:** max-w-7xl centered, responsive grid, card-based sections
- **Cards:** bg-white rounded-xl shadow-sm border border-zinc-200 p-6

## References

- `references/template-base.html` — the HTML skeleton every view should start from (includes delight CSS/JS)
- `references/component-patterns.md` — reusable snippets for stat cards, tables, timelines, badges
- `references/delight-patterns.md` — micro-interactions, animations, copy personality, and empty state patterns

## View Types

1. **Home Dashboard** (`/dashboard`) — unified overview of all modules
2. **Module Views** (`/view contacts`, `/view projects`) — specialized per-module layouts
3. **Custom Views** — ad-hoc reports from natural language ("show me overdue items")

## Output

Write all HTML files to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/`
Open with `open <filepath>` on macOS after writing.
