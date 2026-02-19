# Activity Feed Patterns

HTML component patterns for entity page activity timelines. Use these alongside the base `component-patterns.md` patterns. Tailwind classes must be used exactly as shown.

## Timeline Section Header

Temporal divider between activity groups (Upcoming, This Week, etc.).

```html
<div class="flex items-center gap-3 mt-8 mb-4">
    <h3 class="text-xs font-semibold text-zinc-400 uppercase tracking-wider">This Week</h3>
    <div class="flex-1 h-px bg-zinc-200"></div>
</div>
```

## Email Thread Item (Collapsed)

Shows a thread as one line: subject, message count, latest snippet, date range.

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="mail" class="w-4 h-4 text-blue-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
            <p class="text-sm font-medium truncate">Re: AI for Main+Main</p>
            <span class="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-600 flex-shrink-0">4 emails</span>
        </div>
        <p class="text-xs text-zinc-500 mt-0.5 truncate">"Sounds good, let's sync Thursday to finalize..."</p>
        <p class="text-xs text-zinc-400 mt-0.5">Feb 12 – Feb 18</p>
    </div>
</div>
```

For single emails (thread count = 1), omit the count badge and show only the date (not a range).

## Colleague / Third-Party Email

Activity attributed via company or relationship link. Uses muted zinc styling to distinguish from direct activity.

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="mail" class="w-4 h-4 text-zinc-400"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm"><span class="font-medium">Vahid</span> emailed <span class="font-medium">Daniel</span></p>
        <p class="text-xs text-zinc-500 mt-0.5 truncate">AI for Main+Main — "Here's the updated scope..."</p>
        <p class="text-xs text-zinc-400 mt-0.5">Feb 16</p>
    </div>
</div>
```

## Upcoming Meeting

Future calendar event. Uses green accent to signal "upcoming."

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-green-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="calendar" class="w-4 h-4 text-green-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium">Sprint Planning</p>
        <div class="flex items-center gap-2 mt-0.5">
            <p class="text-xs text-zinc-500">with Sarah, Bob</p>
            <span class="text-xs text-zinc-300">·</span>
            <p class="text-xs text-zinc-500">8:30 – 9:15am</p>
        </div>
        <p class="text-xs text-green-600 font-medium mt-0.5">in 2 days</p>
    </div>
</div>
```

## Past Meeting (Calendar Only)

A past calendar event with no linked transcript.

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="calendar" class="w-4 h-4 text-zinc-400"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium">Kickoff Call</p>
        <p class="text-xs text-zinc-500 mt-0.5">with Sarah, Daniel · 45 min</p>
        <p class="text-xs text-zinc-400 mt-0.5">Feb 10</p>
    </div>
</div>
```

## Meeting + Transcript (Merged)

When a calendar event and transcript match (same day, overlapping participants), merge into a rich meeting item.

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-purple-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="mic" class="w-4 h-4 text-purple-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium">Sprint Planning with Sarah, Bob</p>
        <p class="text-xs text-zinc-600 mt-1 line-clamp-2">Discussed timeline revisions. Agreed on March 15 delivery. Sarah flagged risk on design resources.</p>
        <div class="flex items-center gap-3 mt-1.5">
            <span class="text-xs text-zinc-400">32 min</span>
            <span class="text-xs text-amber-600">2 open commitments</span>
        </div>
        <p class="text-xs text-zinc-400 mt-0.5">Tuesday, Feb 17</p>
    </div>
</div>
```

## CRM Interaction

Manual or auto-generated interaction log entry (call, message, etc.).

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="message-circle" class="w-4 h-4 text-blue-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
            <p class="text-sm font-medium">Call</p>
            <span class="text-xs text-zinc-300">·</span>
            <p class="text-sm text-zinc-700">Discussed timeline</p>
        </div>
        <p class="text-xs text-zinc-500 mt-0.5 truncate">Agreed to push deadline to March. Will send revised scope.</p>
        <p class="text-xs text-zinc-400 mt-0.5">Feb 15</p>
    </div>
</div>
```

Use icons by interaction type: `phone` for calls, `mail` for emails, `calendar` for meetings, `message-circle` for messages.

## Note

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="file-text" class="w-4 h-4 text-zinc-400"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm text-zinc-700 line-clamp-2">Met at the DevOps conference. Interested in our infrastructure monitoring approach. Wants to reconnect in Q2.</p>
        <p class="text-xs text-zinc-400 mt-0.5">Feb 8</p>
    </div>
</div>
```

## Commitment — Open

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="circle-dot" class="w-4 h-4 text-amber-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm"><span class="font-medium">You</span>: Send updated proposal</p>
        <div class="flex items-center gap-2 mt-0.5">
            <p class="text-xs text-zinc-500">from Sprint Planning call</p>
            <span class="text-xs text-zinc-300">·</span>
            <p class="text-xs text-amber-600">due Friday</p>
        </div>
    </div>
</div>
```

## Commitment — Overdue

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="alert-circle" class="w-4 h-4 text-red-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm"><span class="font-medium">You</span>: Send proposal</p>
        <div class="flex items-center gap-2 mt-0.5">
            <p class="text-xs text-zinc-500">from Sprint Planning call</p>
            <span class="text-xs text-zinc-300">·</span>
            <p class="text-xs text-red-600 font-medium">overdue by 3 days</p>
        </div>
    </div>
</div>
```

## Follow-up — Due

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="clock" class="w-4 h-4 text-amber-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium">Follow up re: brand guidelines</p>
        <p class="text-xs text-amber-600 mt-0.5">due tomorrow</p>
    </div>
</div>
```

## Follow-up — Overdue

```html
<div class="flex gap-3 py-3 border-b border-zinc-50">
    <div class="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0 mt-0.5">
        <i data-lucide="alert-triangle" class="w-4 h-4 text-red-600"></i>
    </div>
    <div class="flex-1 min-w-0">
        <p class="text-sm font-medium">Follow up re: budget approval</p>
        <p class="text-xs text-red-600 font-medium mt-0.5">overdue — was due Feb 14</p>
    </div>
</div>
```

## Action Items Card

Appears at the top of the page when there are overdue commitments, upcoming follow-ups, or other items needing attention. **Only render this card when there are items to show.**

```html
<div class="bg-amber-50 border border-amber-200 rounded-xl p-5">
    <div class="flex items-center gap-2 mb-3">
        <i data-lucide="alert-circle" class="w-5 h-5 text-amber-600"></i>
        <h3 class="text-sm font-semibold text-amber-900">Needs Attention</h3>
    </div>
    <ul class="space-y-2">
        <li class="flex items-start gap-2">
            <i data-lucide="alert-circle" class="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0"></i>
            <span class="text-sm text-zinc-800">Overdue: Send proposal — was due Feb 14</span>
        </li>
        <li class="flex items-start gap-2">
            <i data-lucide="clock" class="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0"></i>
            <span class="text-sm text-zinc-800">Follow up re: brand guidelines — due tomorrow</span>
        </li>
    </ul>
</div>
```

When items include both overdue (red) and upcoming (amber), list overdue first.

## Contact Details Sidebar Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="user" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Contact Details</h3>
    </div>
    <dl class="space-y-3 text-sm">
        <div>
            <dt class="text-zinc-400 text-xs">Company</dt>
            <dd class="font-medium">Main + Main</dd>
        </div>
        <div>
            <dt class="text-zinc-400 text-xs">Role</dt>
            <dd>Managing Partner</dd>
        </div>
        <div>
            <dt class="text-zinc-400 text-xs">Email</dt>
            <dd class="text-blue-600">daniel@mainandmain.ca</dd>
        </div>
        <div>
            <dt class="text-zinc-400 text-xs">Phone</dt>
            <dd>+1 (416) 555-1234</dd>
        </div>
    </dl>
    <!-- Missing fields hint (only if data is missing) -->
    <p class="text-xs text-zinc-400 mt-4 pt-3 border-t border-zinc-100">Missing: phone, role</p>
</div>
```

Omit fields that are NULL/empty. Show the "Missing:" hint only if 2+ fields are empty.

## Related Contacts Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="users" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Related Contacts</h3>
    </div>
    <div class="space-y-2.5">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm font-medium">Sarah Chen</p>
                <p class="text-xs text-zinc-500">colleague at Main + Main</p>
            </div>
        </div>
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm font-medium">Vahid Jozi</p>
                <p class="text-xs text-zinc-500">referrer</p>
            </div>
        </div>
    </div>
</div>
```

## Active Projects Card

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="folder-open" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Active Projects</h3>
    </div>
    <div class="space-y-3">
        <div>
            <div class="flex items-center justify-between">
                <p class="text-sm font-medium">Rebrand</p>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">Active</span>
            </div>
            <div class="flex items-center gap-2 mt-1">
                <div class="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 rounded-full" style="width: 60%"></div>
                </div>
                <span class="text-xs text-zinc-400">3/5 tasks</span>
            </div>
        </div>
    </div>
</div>
```

## Relationship Health Indicator

Compact display of relationship trajectory and depth. Only render when Conversation Intelligence module has data for this contact.

```html
<div class="bg-white rounded-xl shadow-sm border border-zinc-200 p-5">
    <div class="flex items-center gap-2 mb-4">
        <i data-lucide="heart-pulse" class="w-5 h-5 text-zinc-400"></i>
        <h3 class="text-sm font-semibold">Relationship</h3>
    </div>
    <div class="flex items-center gap-3 mb-3">
        <!-- Trajectory arrow + label -->
        <div class="flex items-center gap-1.5">
            <i data-lucide="trending-up" class="w-4 h-4 text-green-600"></i>
            <span class="text-sm font-medium text-green-700">Strengthening</span>
        </div>
        <span class="text-xs text-zinc-300">·</span>
        <span class="text-sm text-zinc-600">Collaborative</span>
    </div>
    <div class="space-y-1.5 text-xs text-zinc-500">
        <div class="flex justify-between">
            <span>Meeting frequency</span>
            <span class="font-medium text-zinc-700">4/month</span>
        </div>
        <div class="flex justify-between">
            <span>Commitment follow-through</span>
            <span class="font-medium text-zinc-700">85%</span>
        </div>
        <div class="flex justify-between">
            <span>Avg talk ratio</span>
            <span class="font-medium text-zinc-700">45%</span>
        </div>
    </div>
</div>
```

Trajectory icons: `trending-up` (green) for strengthening, `minus` (zinc) for stable, `trending-down` (amber) for cooling, `alert-triangle` (red) for at_risk.

## Older Section (Collapsed)

Use native `<details>` for zero-JS collapsing.

```html
<details class="mt-6">
    <summary class="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer hover:text-zinc-600">
        <i data-lucide="chevron-right" class="w-4 h-4"></i>
        12 more items from Nov 2025 – Jan 2026
    </summary>
    <div class="mt-3 space-y-0">
        <!-- Older timeline items rendered here, same components as above -->
    </div>
</details>
```

## Entity Page Header

```html
<header class="mb-8">
    <div class="flex items-start justify-between">
        <div>
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
                    <span class="text-lg font-bold text-blue-700">DB</span>
                </div>
                <div>
                    <h1 class="text-2xl font-bold">Daniel Byrne</h1>
                    <p class="text-sm text-zinc-500">Managing Partner at Main + Main</p>
                </div>
            </div>
            <!-- Tags -->
            <div class="flex items-center gap-2 mt-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">client</span>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">real estate</span>
            </div>
        </div>
        <!-- Quick stats -->
        <div class="flex items-center gap-4 text-sm text-zinc-500">
            <div class="flex items-center gap-1.5">
                <i data-lucide="mail" class="w-4 h-4"></i>
                <span>12 emails</span>
            </div>
            <div class="flex items-center gap-1.5">
                <i data-lucide="calendar" class="w-4 h-4"></i>
                <span>4 meetings</span>
            </div>
            <div class="flex items-center gap-1.5">
                <i data-lucide="clock" class="w-4 h-4"></i>
                <span>2 days ago</span>
            </div>
        </div>
    </div>
</header>
```

The avatar initials are derived from the contact's name (first letter of first + last name). Background color: `blue-100` for individuals, `zinc-200` for companies.

## Tags

Use the tag's `color` field from the database if available. Fallback to `bg-zinc-100 text-zinc-600`.
