# Monday Morning Meeting Brief — Benji's

Pull data from the past 7 days across email, Asana, and Slack.
Then save a Gmail draft in kerry@benjis.com for Kerry to review before the 7am Monday meeting.

Recipients: jp@benjis.com, emma@benjis.com, marissa@benjis.com, ops@benjis.com, ximena@benjis.com

Asana project for all tasks: 1211720233228134 (Benji's Ops)

Asana user GIDs:
- Kerry: 1212818323340611
- JP: 1212913237133682
- Emma: 1211720312484677
- Marissa: 1213455306396332
- Nawid: 1211785219260749
- Omid: 1213746207577340
- Ximena: 1211785219260720

Tag all tasks created by this brief with: [Monday Brief YYYY-MM-DD] in the task notes.

---

## Step 0 — Carryover: Check Last Week's Action Items

Search Asana for tasks tagged from last Monday's brief:
- Use search_tasks with text "[Monday Brief" and modified_on_after = 13 days ago
- Check which are completed vs. still open
- Open/incomplete tasks = carryover — these appear at the TOP of the agenda

---

## Step 1 — Email

Run: `python3 shared/monday_brief.py fetch-gmail`

Parse the JSON output. Look for: client issues, escalations, items flagged for the Monday meeting, requests from the team.

---

## Step 2 — Asana

Use Asana MCP tools:
- `get_my_tasks`: Kerry's assigned tasks, focus on incomplete and overdue
- `search_tasks`: tasks modified or created in the past week across all projects

Note: overdue items, blocked tasks, decisions needed, new requests.

---

## Step 3 — Slack

Search the Benji's Slack workspace for the past 7 days. Search each channel separately:
- #general
- #partners
- #finance-client-invoicing
- #new-development-pipeline

Look for action items, open questions, requests to Kerry or management.
Note: decisions made, decisions still pending, blockers, team updates.

---

## Step 4 — Synthesize

Write a meeting agenda. Structure:

**Carryover** — incomplete items from last Monday's brief. Mark each as OPEN with the original owner.

**Action Items** — new things needing a decision or follow-up this week. Include owner name for each.

**Updates to Share** — brief status the team should know.

**Open Questions** — items needing group discussion.

**FYI** — informational only, no action required. Omit if empty.

Only include sections with real content. Keep it tight — cut anything vague or redundant.

### What must always be included (never omit these categories):

- **New inbound leads** — any new prospect, registration form, referral, or walkthrough request. Include estimated value and who owns the next step.
- **Active sales pipeline** — potential client handoffs, calls being scheduled, warm prospects in discussion. These are high-value and always belong on the agenda.
- **Ximena's lead updates** — Ximena owns business development and new client outreach. Always surface: leads she's working, walkthroughs scheduled or pending, and any pipeline activity she reported in Slack or email.
- **Client relationship issues** — any client expressing concern, waiting on something, or flagged as at-risk.
- **Decisions that need the group** — anything where a partner needs to weigh in before work can proceed.

The brief should read like a real management meeting agenda — not a filtered task list. If it happened in the business this week and it affects anyone in the room, include it.

---

## Step 5 — Create Asana Tasks

For every NEW item in Action Items (skip carryover — those tasks already exist), create an Asana task:
- Project: 1211720233228134
- Assignee: use the GID map above based on the owner name in the agenda
- Due date: urgent items today/tomorrow; others due Friday of current week
- Notes: include context from the source (email/Slack/Asana), end with `[Monday Brief YYYY-MM-DD]`

---

## Step 6 — Create Draft

Run: `python3 shared/monday_brief.py create-draft --subject "Monday Morning Meeting — [date]" --body "[HTML]"`

HTML format:
- Open with "Hi team,"
- Carryover section first (if any), styled in red to signal unresolved items
- Then Action Items (with owner), Updates, Open Questions, FYI
- Bold section headers, bullet points
- Close with "Kerry"

The draft will appear in kerry@benjis.com Gmail for Kerry to review and send.
