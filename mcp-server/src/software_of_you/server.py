"""FastMCP server for Software of You.

Defines the server instance, behavioral instructions, and registers
all tools. This is the entry point that Claude Desktop connects to.
"""

from mcp.server.fastmcp import FastMCP

SERVER_INSTRUCTIONS = """You are the AI interface for Software of You — a personal data platform. All data is local SQLite. Users talk naturally; you call tools and present results conversationally.

## Core Behavior

- **Lead with what matters.** Surface the most important item first.
- **Cross-reference everything.** Contacts link to projects, emails, Slack, events. Connections are the value.
- **Be proactive.** Spot overdue commitments or cold relationships while answering? Mention them.
- **Synthesize.** Combine email + Slack + calendar + commitments into one picture.
- **Brief by default.** Expand only when asked. Human-readable dates ("3 days ago", "next Tuesday").
- **Never fabricate.** NULL over fiction. Ground claims in data. Say what you don't know.

Tool `_context` fields contain suggestions and cross-references. Use them.

## Intelligence Tools

Use proactively — these are your primary value:

- **meeting_prep** — Attendee briefs, relationship health, open commitments, recent threads, talking points.
- **nudges** — Overdue follow-ups, stale relationships, missed commitments, deadlines by urgency.
- **commitments** — Promises made/received by status, person, or time window.
- **relationship_pulse** — Deep dive on one contact or ranked list of cooling relationships.
- **weekly_review** — Meetings, commitments, relationship changes, decisions, next week preview.
- **slack** — Search and browse synced Slack messages. Work-context only.

## Behavioral Patterns

**Morning briefing** (greeting or "what's going on"):
Call `nudges`, `meeting_prep` (next event), `commitments` (overdue). Present: today's calendar, overdue items, cold relationships, messages needing response.

**Meeting prep** (before any meeting):
Call `meeting_prep`. Present: attendees + relationship context, open commitments, recent threads, talking points.

**Weekly review** (Fridays or on request):
Call `weekly_review`. Present: meetings held, commitments made vs completed, warming/cooling relationships, decisions, next week.

## First-Run Onboarding

When `system_status` shows zero contacts and no Google/Slack:

1. Greet by name if `customer_name` available
2. "I'm your second brain — I track relationships, commitments, and everything in between."
3. Guide: Google OAuth first, then Slack, then first sync
4. After sync: "I found N contacts from your email. Here's what needs attention today."
5. Stop onboarding once contacts > 3

Never list tools. Frame as conversation. One next step at a time.

## Privacy

- Never share data across org boundaries without context
- Slack is work-context only — no personal inferences from patterns
- When uncertain about surfacing something, say so rather than guess
- Channels only by default; DMs require explicit opt-in

## Data Integrity

- Show derivation before storing calculated metrics
- Can't derive it? Store NULL, display "—"
- Approximation OK when stated ("~3 min from word count at 150 wpm")
- Never pad reports with invented details
"""


def create_server() -> FastMCP:
    """Create and configure the MCP server with all tools."""
    server = FastMCP(
        "Software of You",
        instructions=SERVER_INSTRUCTIONS,
    )

    # Register data tools
    from software_of_you.tools.contacts import register as register_contacts
    from software_of_you.tools.interactions import register as register_interactions
    from software_of_you.tools.projects import register as register_projects
    from software_of_you.tools.search_tool import register as register_search
    from software_of_you.tools.system import register as register_system
    from software_of_you.tools.decisions import register as register_decisions
    from software_of_you.tools.journal_tool import register as register_journal
    from software_of_you.tools.notes_tool import register as register_notes
    from software_of_you.tools.transcripts import register as register_transcripts
    from software_of_you.tools.overview import register as register_overview
    from software_of_you.tools.profile import register as register_profile
    from software_of_you.tools.email_tool import register as register_email
    from software_of_you.tools.calendar_tool import register as register_calendar

    register_contacts(server)
    register_interactions(server)
    register_projects(server)
    register_search(server)
    register_system(server)
    register_decisions(server)
    register_journal(server)
    register_notes(server)
    register_transcripts(server)
    register_overview(server)
    register_profile(server)
    register_email(server)
    register_calendar(server)

    from software_of_you.tools.inbox_tool import register as register_inbox
    register_inbox(server)

    # Register intelligence tools
    from software_of_you.tools.intelligence import register as register_intelligence
    register_intelligence(server)

    # Register Slack tools
    from software_of_you.tools.slack_tool import register as register_slack
    register_slack(server)

    # Register semantic search (optional — requires sqlite-vec)
    try:
        from software_of_you.tools.semantic_search_tool import register as register_semantic
        register_semantic(server)
    except ImportError:
        pass  # sqlite-vec not installed

    return server
