# Monday Morning Meeting Brief — Benji's

Pull data from the past 7 days across email, Asana, and Slack.
Then save a Gmail draft in kerry@benjis.com for Kerry to review before the 7am Monday meeting.

Recipients: jp@benjis.com, emma@benjis.com, marissa@benjis.com, ops@benjis.com, ximena@benjis.com

## Step 1 — Email

Run: `python3 shared/monday_brief.py fetch-gmail`

Parse the JSON output. Look for: client issues, escalations, items flagged for the Monday meeting, requests from the team.

## Step 2 — Asana

Use Asana MCP tools:
- `get_my_tasks`: Kerry's assigned tasks, focus on incomplete and overdue
- `search_tasks`: tasks modified or created in the past week across all projects

Note: overdue items, blocked tasks, decisions needed, new requests.

## Step 3 — Slack

Search the Benji's Slack workspace for the past 7 days.
Search relevant channels for action items, open questions, requests to Kerry or management.
Note: decisions made, decisions still pending, blockers, team updates.

## Step 4 — Synthesize

Write a meeting agenda. Only include sections with real content — omit empty ones:

**Action Items** — specific things needing a decision or follow-up this week  
**Updates to Share** — brief status the team should know  
**Open Questions** — items needing group discussion  
**FYI** — informational only, no action required  

Keep it tight. Cut anything vague or redundant.

## Step 5 — Create Draft

Run: `python3 shared/monday_brief.py create-draft --subject "Monday Morning Meeting — [date]" --body "[HTML]"`

HTML format:
- Open with "Hi team,"
- Bold section headers
- Bullet points for each item
- Close with "Kerry"

The draft will appear in kerry@benjis.com Gmail for Kerry to review and send.
