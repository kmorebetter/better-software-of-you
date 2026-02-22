# Software of You — Feature Brief

A reference document for marketing copy, landing pages, onboarding, and sales conversations.

---

## CRM

**What it does:** Tracks every person you work with — contacts, interaction history, follow-up nudges, relationship health scores.

**How it's used:**
- Add contacts naturally: *"Add Sarah Chen, VP Eng at Acme, met at SaaStr"*
- Log interactions: *"Had a good call with Marcus, he's moving forward with the proposal"*
- Get nudges when relationships go cold automatically
- Relationship scores derived from interaction frequency and email tone — not something you manually set

**What it solves:** The problem where someone important quietly disappears because you forgot to follow up. The system surfaces *"You haven't talked to Daniel in 3 weeks and you have an open commitment with him"* — you didn't have to remember to check.

**Example:** *"Who haven't I talked to in the last 30 days that I should follow up with?"* → Claude queries interaction history across all contacts and gives you a ranked list with context.

---

## Project Tracker

**What it does:** Projects and tasks linked to the people driving them. Milestones, status, blockers — all connected to CRM.

**How it's used:**
- *"Create a project for the Meridian rebrand, client is Rebecca Chen, target close Q2"*
- *"Mark the proposal task complete, add a blocker: waiting on legal review"*
- Ask for a full project brief that includes client relationship history, open commitments, and recent communications

**What it solves:** The disconnect between your project tool and your relationship context. In every other tool, a project is a project. Here, the Meridian project knows Rebecca is the client, knows you last talked 4 days ago, knows there are 2 open commitments from your last call.

**Example:** *"What's the status on everything in flight right now?"* → A ranked list of active projects with health indicators, days since last activity, and who to contact next.

---

## Gmail

**What it does:** Syncs your inbox, links emails to contacts and projects, lets you compose with full relationship context.

**How it's used:**
- Auto-syncs every 15 minutes when you open a view
- *"Show me everything from Rebecca in the last 2 weeks"*
- *"Draft a follow-up to Daniel about the proposal — he's the Main+Main guy, real estate AI"* → Claude writes the email knowing the full thread history, your last meeting, and any open commitments

**What it solves:** The copy-paste tax. Right now to get Claude to help you write an email, you have to paste in the thread, explain who the person is, summarize what's happened. With SoY, Claude already knows all of it.

**Example:** *"Who in my inbox hasn't heard from me in over a week?"* → Cross-references your sent mail against CRM contacts and surfaces gaps.

---

## Calendar

**What it does:** Syncs events for the past 7 and next 14 days, links attendees to contacts, gives you scheduling context.

**How it's used:**
- *"What's on my calendar this week?"* → Shows events with attendee context pulled from CRM
- *"Who am I meeting tomorrow and what should I know going in?"* → Claude pulls the contact's relationship history, recent emails, open commitments, and project status
- Pre-meeting briefs generated automatically

**What it solves:** Walking into meetings cold. You know the name, you know the time — but you're re-reading old emails 5 minutes before the call. SoY surfaces everything relevant automatically.

**Example:** *"Generate prep notes for my 2pm with Marcus"* → Last 3 emails, open commitments, project status, topics from previous meetings, suggested questions.

---

## Conversation Intelligence

**What it does:** Import any meeting transcript (Zoom, Gemini, Otter, paste-in), extract commitments, measure talk ratios, build relationship health over time.

**How it's used:**
- `/import-call` → paste transcript → Claude extracts who said what, commitments made by each party, coaching insights about your communication patterns
- Commitments automatically tracked and surfaced as nudges if not resolved
- Talk ratio, question frequency, longest monologue — all derived from the actual text, not estimated

**What it solves:** The fact that 90% of what happens in a meeting disappears within 24 hours. Commitments get lost. Patterns in how you communicate never get examined. This captures and structures both.

**Example:** After 10 calls with a key client, Claude can tell you: *"You typically talk 68% of the time with Rebecca. In your last 3 calls, the topic has shifted from logistics to pricing. You have 4 open commitments she's waiting on."*

---

## Decision Log

**What it does:** Structured decision records — the options you considered, the rationale, the expected outcome, and when the outcome becomes knowable. Grounded in Annie Duke's process/outcome framework.

**How it's used:**
- *"Log a decision: we're going with the annual pricing model over monthly. Options were X, Y, Z. Rationale: lower churn risk, better cash flow. Revisit in 90 days."*
- Decisions are linked to contacts who were involved and projects they affect
- Revisit prompts surface when the outcome date arrives

**What it solves:** Decision amnesia — the phenomenon where six months later you can't remember why you made a call, so you either relitigate it or repeat the same mistake. It also separates process quality from outcome quality: a good decision with a bad outcome is still a good decision.

**Example:** *"What decisions have I made about pricing in the last year?"* → Full history with rationale, who was involved, and outcomes where they've been recorded.

---

## Journal

**What it does:** Daily entries with mood and energy markers, automatically cross-referenced to contacts and projects you mention by name.

**How it's used:**
- *"Journal: Had a draining call with the Meridian team today. Rebecca seemed checked out. Wondering if the timeline is too aggressive."* → Entry saved, linked to Rebecca and Meridian project automatically
- Mood/energy trends visible over time
- Cross-references make the journal useful beyond reflection — it becomes relationship and project signal

**What it solves:** Qualitative context that never makes it into any other system. The fact that Rebecca seemed disengaged on a Thursday in January is exactly the kind of signal that would make your next project review richer — but it lives nowhere unless you capture it here.

**Example:** *"How have I been feeling about the Meridian project over time?"* → Claude surfaces all journal entries mentioning the project, showing sentiment arc across weeks.

---

## Notes

**What it does:** Standalone notes with #hashtag tagging and automatic cross-referencing. First-class content, not just attachments.

**How it's used:**
- *"Note: the new AI compliance framework from the EU affects every enterprise deal. #legal #enterprise"*
- Notes automatically link to any contact or project mentioned by name
- Pin important notes to surface them in views
- *"Show me everything tagged #enterprise"*

**What it solves:** The friction between "I need to capture this right now" and "I need to find this later." Notion is powerful but heavy. Slack is fast but lossy. This is structured enough to be findable, light enough to use in the moment.

**Example:** A note about a competitor's pricing surfaces in the entity page for every contact you've discussed that competitor with — you didn't have to tag them manually.

---

## Cross-Module Intelligence (the whole point)

Every module above works alone. Together they compound:

- **"Prepare me for my week"** → Calendar events + who you're meeting + their email history + open commitments + project status + relationship health scores
- **"What should I be worried about right now?"** → Nudges: overdue commitments, cold relationships, stalled projects, unresolved decisions with past revisit dates
- **"Draft a proposal for Rebecca"** → Claude has her CRM profile, your full email thread, meeting notes, the project brief, and the decision history. You describe the ask. It writes from context.
- **Weekly Review** → Auto-generated from everything that happened: who you talked to, what moved, what didn't, what needs attention next week

The marketing angle isn't any individual module. It's that **your AI finally has the same context you do** — and can act on it.
