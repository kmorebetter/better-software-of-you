# Delight Patterns

Micro-interactions, animations, and personality that make Software of You feel alive without being distracting. The philosophy is **quiet sophistication** — things that feel satisfying the way a well-made notebook does.

**Read this file before generating any HTML view.** All CSS and JS below are included in `template-base.html` and available on every page.

## Principles

1. **Delight enhances, never blocks.** Animations are fast (<400ms). Nothing delays content.
2. **Respect the brand.** Warm, direct, calm. No confetti, no "herding pixels", no wacky copy.
3. **Respect the user.** `prefers-reduced-motion` disables all animation. No sound. No forced interactions.
4. **Less is special.** If everything moves, nothing moves. Apply delight selectively.

---

## CSS Classes (available on all pages)

### Card Entrance — `.delight-card`

Fades cards up with a stagger on page load. Apply to direct children of a grid container.

```html
<!-- Cards stagger automatically based on child position -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 delight-card">...</div>
    <div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 delight-card">...</div>
    <div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 delight-card">...</div>
</div>
```

The stagger is 50ms per item (child 1 = 0ms, child 2 = 50ms, etc.) up to 12 children. For grids with more than 12 items, the JS `initCardStagger()` function handles arbitrary counts.

**When to use:** Main content cards, stat card grids, any primary card layout. **Not** for table rows or list items (use `.delight-row` instead).

### Card Hover Lift — `.delight-hover`

Subtle upward shift + shadow on hover. Makes clickable cards feel responsive.

```html
<a href="contact-sarah.html" class="bg-white rounded-xl shadow-sm border border-zinc-200 p-6 delight-card delight-hover">
    <!-- Card content -->
</a>
```

**When to use:** Any card that links somewhere. Entity cards in sidebar, project cards, contact cards. **Not** for non-interactive cards (stat displays, readonly sections).

### Stat Countup — `data-countup`

Numbers animate from 0 to their value over 600ms with ease-out cubic.

```html
<p class="text-2xl font-bold" data-countup="24">24</p>
```

The inner text is the fallback (for no-JS). The `data-countup` attribute drives the animation. **Only use on integers.** For formatted numbers, use `data-countup-prefix` and `data-countup-suffix`:

```html
<p class="text-2xl font-bold" data-countup="87" data-countup-suffix="%">87%</p>
```

**When to use:** Dashboard stat cards, summary numbers at the top of any view, score displays. **Not** for inline numbers in sentences or table cells.

### Progress Bar Fill — `.delight-progress`

Animates width from 0% to the set value on page load.

```html
<div class="w-full bg-zinc-100 rounded-full h-2">
    <div class="bg-blue-600 h-2 rounded-full delight-progress" style="width: 65%"></div>
</div>
```

**When to use:** Any progress indicator — project completion, relationship scores, talk ratios.

### Row Hover — `.delight-row`

Smooth background transition on hover instead of instant Tailwind `hover:bg-zinc-50`.

```html
<tr class="border-b border-zinc-50 delight-row">
    <td class="py-2.5 font-medium">Item Name</td>
</tr>
```

**When to use:** All table rows. Replaces `hover:bg-zinc-50` — do not combine both.

### Section Scroll Reveal — `.delight-section`

Sections below the fold fade in as they scroll into view. Uses IntersectionObserver.

```html
<div class="delight-section">
    <h2 class="text-lg font-semibold mb-4">Recent Activity</h2>
    <!-- Section content -->
</div>
```

**When to use:** Content sections that start below the visible viewport. Typically the 3rd+ card in a long page. **Not** for above-the-fold content (that should use `.delight-card` entrance instead).

### Link Underline — `.delight-link`

Animated underline that slides in from left on hover.

```html
<a href="contact-sarah.html" class="text-blue-600 font-medium delight-link">Sarah Chen</a>
```

**When to use:** Contact name links, project links, any inline text link. Works alongside `hover:text-blue-800`.

### Checkmark Draw — `.delight-check` (SVG)

An SVG checkmark that draws itself. Use for "all clear" states or completion indicators.

```html
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-green-600">
    <polyline points="4 12 9 17 20 7" class="delight-check"></polyline>
</svg>
```

**When to use:** "All clear" empty states, task completion indicators, success moments.

---

## Sidebar Delight

### Active Page Dot

The currently active sidebar item gets a breathing blue dot:

```html
<a class="sidebar-item active" href="dashboard.html">
    <span class="sidebar-active-dot"></span>
    <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
    <span>Dashboard</span>
</a>
```

The dot is a 6px blue circle with a slow pulse animation (2.5s cycle). Add it to the active sidebar item only.

### Logo Hover

The sidebar hexagon icon has a smooth 360° rotation on hover. This is built into the sidebar CSS — no extra class needed. Just ensure the logo icon has the `.sidebar-logo-icon` class.

---

## Copy Personality

### Greeting Variations

The dashboard greeting should rotate between variations. Use the `getTimeGreeting(name)` JS function:

| Time of Day | Variations |
|---|---|
| Morning (before 12pm) | "Good morning, {name}" · "Morning, {name}" · "Hey {name} — here's your day" |
| Afternoon (12pm–5pm) | "Good afternoon, {name}" · "Afternoon, {name}" · "Hey {name} — here's what's happening" |
| Evening (after 5pm) | "Good evening, {name}" · "Evening, {name}" · "Hey {name} — here's where things stand" |

For the dashboard, render the greeting with JS:
```html
<h1 class="text-2xl font-bold text-zinc-900" id="greeting">Good morning</h1>
<script>
    var greetingEl = document.getElementById('greeting');
    if (greetingEl) greetingEl.textContent = getTimeGreeting('Kerry');
</script>
```

### Empty States (Warm)

Replace generic empty states with contextual, encouraging copy. Match the icon to the context.

| Context | Icon | Primary Text | Secondary Text |
|---|---|---|---|
| No contacts | `coffee` | "Your network starts here" | "Add someone you work with — I'll start tracking from there" |
| No projects | `compass` | "Ready when you are" | "Start a project and I'll help you keep it moving" |
| No emails | `inbox` | "Inbox clear" | "Nothing waiting for your attention" |
| No calendar events | `sun` | "Schedule's open" | "No events coming up — enjoy the space" |
| No journal entries | `feather` | "What's on your mind?" | "Your journal is empty — start with how today went" |
| No decisions | `scale` | "No decisions logged yet" | "Next time you're weighing options, walk me through it" |
| No notes | `pen-tool` | "Blank page, infinite potential" | "Capture a thought — I'll cross-reference it automatically" |
| No transcripts | `mic` | "No conversations analyzed" | "Upload a call transcript and I'll extract the insights" |
| No nudges (all clear) | `check-circle` | "Nothing needs your attention" | "All clear — nice work" |
| No search results | `search` | "No matches" | "Try different keywords or a broader category" |
| Quiet week (weekly review) | `coffee` | "Quiet week" | "Not much to report — that's fine too" |

**Format:**
```html
<div class="text-center py-12">
    <div class="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mx-auto">
        <i data-lucide="coffee" class="w-6 h-6 text-zinc-400"></i>
    </div>
    <p class="text-sm text-zinc-600 mt-3 font-medium">Your network starts here</p>
    <p class="text-xs text-zinc-400 mt-1">Add someone you work with — I'll start tracking from there</p>
</div>
```

Note the differences from the old pattern: larger icon in a circle background, `text-zinc-600` (not 400) for the primary text, slightly more padding (`py-12`), and `font-medium` on the primary line. The copy speaks in first person ("I'll") to match the brand voice.

### "All Clear" Celebration

When a section that normally has items (nudges, overdue commitments, pending follow-ups) is empty, use the checkmark draw animation:

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

### Tooltip Human Interpretations

When showing relationship scores, add a `title` attribute with a human-readable interpretation:

| Score Range | Interpretation |
|---|---|
| 90–100 | "Very close — you talk all the time" |
| 70–89 | "Strong relationship — regular contact" |
| 50–69 | "Solid — you check in periodically" |
| 30–49 | "Casual — might be worth reaching out" |
| 0–29 | "Distant — been a while since you connected" |

```html
<span class="text-sm font-semibold" title="Strong relationship — regular contact">78</span>
```

---

## Time-Aware Accents

The dashboard greeting card can adapt its accent color based on time of day. This is a subtle tint, not a theme change.

```html
<header class="mb-8 delight-card">
    <div class="flex items-center justify-between p-6 rounded-xl" id="greeting-card">
        <!-- Greeting content -->
    </div>
</header>
<script>
    var hour = new Date().getHours();
    var card = document.getElementById('greeting-card');
    if (card) {
        if (hour < 12) card.style.background = 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)';
        else if (hour < 17) card.style.background = 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)';
        else card.style.background = 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)';
    }
</script>
```

| Time | Gradient | Feel |
|---|---|---|
| Morning | warm amber (`#fffbeb` → `#fef3c7`) | Warm, energizing |
| Afternoon | light blue (`#f0f9ff` → `#e0f2fe`) | Clear, focused |
| Evening | soft violet (`#f5f3ff` → `#ede9fe`) | Calm, winding down |

**Only use on the dashboard greeting.** Other pages should not have time-aware styling.

---

## What NOT to Do

- **No confetti, no party effects.** The brand is calm.
- **No sound effects.** Ever.
- **No loading messages** like "herding pixels" or "teaching robots to dance." If a view needs a loading state, use a clean skeleton screen.
- **No Easter eggs.** The product is a tool, not a toy.
- **No gamification** (badges, streaks, points). The user's data is the reward.
- **No forced animation** — everything degrades gracefully with `prefers-reduced-motion`.
- **Don't animate everything.** If every card bounces and every number counts up and every section fades in, nothing feels special. Be selective.
- **Don't delay content for delight.** All animations run in parallel with content display, never sequentially blocking it.
