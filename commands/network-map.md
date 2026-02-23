---
description: Generate an interactive visual map of your contact network — who you know, how they connect, and relationship health
allowed-tools: ["Bash", "Read", "Write"]
---

# Network Map

Generate an interactive D3.js force-directed network map of the user's contacts. This is a full-screen visualization showing who they know, how contacts connect, and relationship health — all in a single self-contained HTML file.

## Step 1: Read References + Check Modules

Read design references:
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/template-base.html`
- `${CLAUDE_PLUGIN_ROOT}/skills/dashboard-generation/references/navigation-patterns.md`

Check installed modules:
```sql
SELECT name FROM modules WHERE enabled = 1;
```

## Step 2: Gather Data

Query `${CLAUDE_PLUGIN_ROOT}/data/soy.db`. Run all queries in a single `sqlite3` heredoc call for efficiency.

### Always query:

```sql
-- All active contacts with activity counts
SELECT c.id, c.name, c.company, c.role, c.type, c.email,
  (SELECT COUNT(*) FROM activity_log WHERE entity_type = 'contact' AND entity_id = c.id) as activity_count,
  (SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'contact' AND entity_id = c.id) as last_activity
FROM contacts c
WHERE c.status = 'active';

-- Tags for each contact
SELECT et.entity_id as contact_id, t.name as tag_name, t.color
FROM entity_tags et
JOIN tags t ON t.id = et.tag_id
WHERE et.entity_type = 'contact';

-- Generated entity pages (for click-through)
SELECT entity_id, filename FROM generated_views
WHERE entity_type = 'contact' AND view_type = 'entity_page';

-- Navigation links
SELECT view_type, entity_name, filename, updated_at
FROM generated_views
ORDER BY updated_at DESC LIMIT 10;
```

### If CRM installed:

```sql
-- Explicit relationships (these become primary edges)
SELECT cr.contact_id_a, cr.contact_id_b, cr.relationship_type, cr.notes,
  ca.name as name_a, cb.name as name_b
FROM contact_relationships cr
JOIN contacts ca ON ca.id = cr.contact_id_a
JOIN contacts cb ON cb.id = cr.contact_id_b;

-- Interaction counts per contact (for node sizing)
SELECT contact_id, COUNT(*) as interaction_count,
  MAX(occurred_at) as last_interaction
FROM contact_interactions
GROUP BY contact_id;
```

### If Conversation Intelligence installed:

```sql
-- Relationship scores (for node coloring by health)
SELECT rs.contact_id, rs.relationship_depth, rs.trajectory,
  rs.meeting_frequency, rs.commitment_follow_through
FROM relationship_scores rs
INNER JOIN (
  SELECT contact_id, MAX(score_date) as latest
  FROM relationship_scores GROUP BY contact_id
) latest ON rs.contact_id = latest.contact_id AND rs.score_date = latest.latest;
```

### If Calendar installed:

```sql
-- Co-attendance: people who share calendar events (implicit relationship edges)
SELECT ce.contact_ids FROM calendar_events ce
WHERE ce.contact_ids IS NOT NULL AND ce.contact_ids != '';
```

## Step 3: Build the Graph Data

From the gathered data, construct two arrays: `nodes` and `links`.

**Nodes** — each contact becomes a node:
- `id`: contact ID
- `name`: full contact name
- `company`: company name (for clustering and coloring)
- `role`: role/title
- `type`: contact type
- `size`: based on interaction count (more interactions = larger). Range: 8px (no interactions) to 40px (most interactions). Scale linearly.
- `color`: assigned by company from the palette (see below). If Conversation Intelligence is installed, override with relationship health color (green = strong, amber = moderate, red = weak).
- `opacity`: based on recency of last activity. Activity in the last 7 days = 1.0, last 30 days = 0.85, last 90 days = 0.7, older = 0.55.
- `entityPage`: filename from `generated_views` if one exists, otherwise null.
- `tags`: array of `{name, color}` from entity_tags.
- `recentlyActive`: true if last activity within 7 days (drives pulse animation).
- `activityCount`: raw count for tooltip.
- `lastActivity`: human-readable date for tooltip.
- `relationshipDepth`: score from relationship_scores if available.
- `trajectory`: from relationship_scores if available.

**Links** — connections between contacts:
- **Explicit relationships** (from `contact_relationships`): `source`, `target`, `type` (relationship_type), `strength: 3` (thick edge)
- **Same company** (implicit): for contacts sharing a `company` value, create an edge with `type: 'company'`, `strength: 1` (thin edge)
- **Calendar co-attendance** (if available): parse `contact_ids` (comma-separated). For each event, create edges between all pairs of contacts listed. Deduplicate. `type: 'co-attendance'`, `strength: 2`

## Step 4: Generate HTML

Generate a single self-contained HTML file. CDN includes:
- Tailwind CSS: `https://cdn.tailwindcss.com`
- D3.js v7: `https://d3js.org/d3.v7.min.js`
- Lucide icons: `https://unpkg.com/lucide@latest/dist/umd/lucide.min.js`
- Inter font: Google Fonts

### Page Structure

```
Sidebar (from navigation-patterns.md — Network Map active in the People section)

Header card (full width)
├── Title: "Your Network"
├── Subtitle: "X contacts, Y connections"
└── Filter controls: dropdown to filter by company, tag, or type

Main visualization (full width, ~70vh height)
├── SVG with D3 force-directed graph
├── Zoom controls (subtle, bottom-right: zoom in, zoom out, reset)
└── Legend (bottom-left: node size = activity level, colors = companies or health)

Stats bar (4-column grid below visualization)
├── Total contacts
├── Companies represented
├── Strongest connection (most interactions)
└── Most connected person (most edges)

Footer (from navigation-patterns.md)
```

### D3 Force Simulation

Embed ALL graph data and D3 code inline in a `<script>` tag. The key implementation pattern:

```javascript
// Embed data directly
const nodes = [/* node objects from Step 3 */];
const links = [/* link objects from Step 3 */];

// Company color palette
const companyColors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];
const companyColorMap = {};
let colorIdx = 0;
nodes.forEach(n => {
  if (n.company && !companyColorMap[n.company]) {
    companyColorMap[n.company] = companyColors[colorIdx % companyColors.length];
    colorIdx++;
  }
});

// SVG setup with zoom
const svg = d3.select("#network-svg");
const width = svg.node().getBoundingClientRect().width;
const height = svg.node().getBoundingClientRect().height;
const g = svg.append("g");

const zoom = d3.zoom()
  .scaleExtent([0.3, 4])
  .on("zoom", (event) => g.attr("transform", event.transform));
svg.call(zoom);

// Force simulation
const simulation = d3.forceSimulation(nodes)
  .force("link", d3.forceLink(links).id(d => d.id).distance(100))
  .force("charge", d3.forceManyBody().strength(-200))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collision", d3.forceCollide().radius(d => d.size + 5))
  .force("x", d3.forceX(width / 2).strength(0.05))
  .force("y", d3.forceY(height / 2).strength(0.05));

// Draw edges
const link = g.append("g")
  .selectAll("line")
  .data(links)
  .join("line")
  .attr("stroke", d => d.type === 'company' ? "#e4e4e7" : "#d4d4d8")
  .attr("stroke-width", d => d.strength)
  .attr("stroke-opacity", 0.6);

// Draw nodes
const node = g.append("g")
  .selectAll("circle")
  .data(nodes)
  .join("circle")
  .attr("r", d => d.size)
  .attr("fill", d => d.color)
  .attr("stroke", "#d4d4d8")
  .attr("stroke-width", 1.5)
  .attr("opacity", d => d.opacity)
  .attr("cursor", "pointer")
  .call(drag(simulation));

// Draw labels (first name only to avoid clutter)
const label = g.append("g")
  .selectAll("text")
  .data(nodes)
  .join("text")
  .text(d => d.name.split(" ")[0])
  .attr("font-size", "11px")
  .attr("font-family", "Inter, sans-serif")
  .attr("fill", "#3f3f46")
  .attr("text-anchor", "middle")
  .attr("dy", d => d.size + 14)
  .attr("pointer-events", "none");

// Tick update
simulation.on("tick", () => {
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("cx", d => d.x).attr("cy", d => d.y);
  label.attr("x", d => d.x).attr("y", d => d.y);
});

// Drag behavior
function drag(simulation) {
  return d3.drag()
    .on("start", (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x; d.fy = d.y;
    })
    .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
    .on("end", (event, d) => {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null; d.fy = null;
    });
}
```

### Visual Delight Features (required — these make the map feel alive)

**1. Entry animation:** Nodes start clustered near center with small random offsets. The simulation naturally spreads them out over ~2 seconds. Use `simulation.alpha(1).restart()`.

**2. Hover effects:**
- Hovered node scales up 1.3x with a glow: CSS `filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))`
- Connected nodes stay full opacity; all others dim to 0.15 opacity
- Connected edges thicken and turn blue (`#3b82f6`)
- Tooltip appears near the cursor showing: name, company, role, last activity, activity count, relationship depth (if available), trajectory (if available)

```javascript
node.on("mouseover", function(event, d) {
  const connected = new Set();
  links.forEach(l => {
    if (l.source.id === d.id) connected.add(l.target.id);
    if (l.target.id === d.id) connected.add(l.source.id);
  });
  connected.add(d.id);

  node.attr("opacity", n => connected.has(n.id) ? 1 : 0.15);
  link.attr("stroke", l => (l.source.id === d.id || l.target.id === d.id) ? "#3b82f6" : "#e4e4e7")
      .attr("stroke-width", l => (l.source.id === d.id || l.target.id === d.id) ? l.strength + 2 : l.strength)
      .attr("stroke-opacity", l => (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.2);
  label.attr("opacity", n => connected.has(n.id) ? 1 : 0.15);

  d3.select(this).attr("r", d.size * 1.3).style("filter", "drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))");

  // Show tooltip
  showTooltip(event, d);
})
.on("mouseout", function(event, d) {
  node.attr("opacity", n => n.opacity);
  link.attr("stroke", l => l.type === 'company' ? "#e4e4e7" : "#d4d4d8")
      .attr("stroke-width", l => l.strength)
      .attr("stroke-opacity", 0.6);
  label.attr("opacity", 1);
  d3.select(this).attr("r", d.size).style("filter", "none");
  hideTooltip();
});
```

**3. Edge rendering:**
- Default: thin (1-2px), light gray (`#e4e4e7`) for company edges, slightly darker (`#d4d4d8`) for explicit relationships
- Relationship type label on hover (show as small text near edge midpoint)
- Smooth CSS transitions on stroke-width and color changes

**4. Company clustering:**
- Assign each unique company a color from the palette
- Nodes colored by company (fill = company color)
- Same-company edges pull contacts together naturally via the force simulation
- Legend shows company-to-color mapping

**5. Node labels:**
- Show first name only by default
- Full name + role shown in tooltip on hover
- Labels follow nodes during simulation
- Font: Inter, 11px, fill: `#3f3f46`

**6. Drag interaction:**
- Nodes can be dragged to rearrange
- While dragging, node is pinned (fx/fy set)
- On release, node unfreezes and simulation continues
- Other nodes react to the physics during drag

**7. Zoom and pan:**
- D3 zoom behavior attached to SVG
- Scroll to zoom, click-drag on background to pan
- Zoom buttons in bottom-right corner (+ / - / reset)
- Double-click on background resets zoom to fit all nodes

**8. Click behavior:**
- If contact has an entity page (`entityPage` is set), `window.open(entityPage)` to open it
- If no entity page, show a brief tooltip: "Run /entity-page {name} to create a page"

**9. Pulse animation (CSS):**
- Contacts with `recentlyActive: true` get a CSS class that pulses
- Keyframe animation: scale between 1.0 and 1.05 every 3 seconds
- Subtle — not distracting, but enough to notice who's been active

```css
@keyframes pulse-node {
  0%, 100% { r: attr(r); }
  50% { transform: scale(1.05); }
}
```

Use a JS interval to toggle a gentle size oscillation on recently active nodes instead, since SVG `r` can't be animated via CSS keyframes easily. Apply a subtle `transform-origin: center` and `animation: pulse 3s ease-in-out infinite` on the node group.

**10. Filter controls:**
- Dropdown or pill buttons to filter by: company, tag, contact type
- Filtering hides non-matching nodes and their edges (fade out with transition)
- "Show all" button to reset

### Design Rules

- Background: `bg-zinc-50` (`#fafafa`)
- Cards: `bg-white rounded-xl shadow-sm border border-zinc-200 p-6`
- SVG background: white with zinc-200 border, rounded corners
- Default node stroke: `#d4d4d8` (zinc-300)
- Edge default: `#e4e4e7` (zinc-200) for implicit, `#d4d4d8` for explicit
- Edge hover: `#3b82f6` (blue-500)
- Tooltip: white card with zinc border, shadow-lg, rounded-lg, p-3
- Text: `#18181b` (zinc-900) for primary, `#71717a` (zinc-500) for secondary
- Responsive: SVG fills container width. On smaller screens, hide legend, stack stat pills vertically

### Tooltip HTML

The tooltip is a `div` positioned absolutely near the cursor:

```html
<div id="tooltip" class="fixed bg-white border border-zinc-200 rounded-lg shadow-lg p-3 pointer-events-none z-50 hidden" style="max-width: 240px;">
  <div class="font-semibold text-zinc-900 text-sm"></div>
  <div class="text-xs text-zinc-500 mt-0.5"></div>
  <div class="text-xs text-zinc-500 mt-0.5"></div>
  <div class="mt-2 pt-2 border-t border-zinc-100 text-xs text-zinc-400"></div>
</div>
```

Position it with JS on mouseover, offset from cursor by ~12px.

Write the complete HTML to: `${CLAUDE_PLUGIN_ROOT}/output/network-map.html`

## Step 5: Register and Open

Register in generated_views:
```sql
INSERT INTO generated_views (view_type, entity_type, entity_id, entity_name, filename)
VALUES ('network_map', NULL, NULL, 'Network Map', 'network-map.html')
ON CONFLICT(filename) DO UPDATE SET updated_at = datetime('now');
```

Open with: `open "${CLAUDE_PLUGIN_ROOT}/output/network-map.html"`

Tell the user: "Network map opened. X contacts, Y connections. Hover to explore, click to open entity pages, drag to rearrange."
