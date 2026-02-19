---
description: View, create, and manage Google Calendar events
allowed-tools: ["Bash", "Read"]
argument-hint: [today | week | schedule <event> | with <contact name>]
---

# Calendar

Manage Google Calendar events. Database at `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

## Step 1: Check Authentication

```
ACCESS_TOKEN=$(python3 "${CLAUDE_PLUGIN_ROOT}/shared/google_auth.py" token)
```

If this fails: "Calendar isn't connected. Run `/google-setup` to connect your Google account."

## Step 2: Determine the Operation

Parse $ARGUMENTS:

- **No arguments or "today"** → Show today's events
- **"week"** → Show this week's events
- **"tomorrow"** → Show tomorrow's events
- **"schedule <details>"** → Create a new event
- **"with <name>"** → Show events involving a specific contact
- **"free" or "availability"** → Show free slots today/this week

## Viewing Events

**Fetch events from Google Calendar API:**
```bash
# Today's events
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={today_start_iso}&timeMax={today_end_iso}&singleEvents=true&orderBy=startTime"

# This week's events
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={today_start_iso}&timeMax={week_end_iso}&singleEvents=true&orderBy=startTime"
```

Use ISO 8601 format for times (e.g., `2026-02-18T00:00:00Z`).

**Auto-link attendees to contacts:**
For each event's attendees, check:
```sql
SELECT id, name FROM contacts WHERE email = ?;
```

**Cache events locally:**
```sql
INSERT OR REPLACE INTO calendar_events (google_event_id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
```

**Present as a clean schedule:**
```
Today — Wednesday, Feb 18

  9:00 AM   Design review with Jane Smith (Acme)
             📍 Zoom · 1 hour

  1:30 PM   API planning
             With Bob Johnson (Widgets Inc)
             📍 Conference Room B · 45 min

  3:00 PM   Team standup
             📍 Google Meet · 15 min
```

Show contact names (not just emails) when linked. Include location and duration.

## Creating Events

When the user says `/calendar schedule meeting with Jane tomorrow at 2pm about the website`:

1. Parse: attendee (Jane), date/time (tomorrow 2pm), subject (website)
2. Look up Jane's email: `SELECT email FROM contacts WHERE name LIKE '%Jane%';`
3. Look up relevant project if mentioned: `SELECT id FROM projects WHERE name LIKE '%website%';`

**Show the event details and confirm:**

"I'll create this event:

**Meeting: Website Redesign discussion**
📅 Tomorrow (Feb 19) at 2:00 PM — 2:30 PM
👤 Jane Smith (jane@acme.com)
📝 Linked to project: Website Redesign

Create this event?"

**After confirmation, create via API:**
```bash
curl -s -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "Website Redesign discussion",
    "start": {"dateTime": "2026-02-19T14:00:00", "timeZone": "America/New_York"},
    "end": {"dateTime": "2026-02-19T14:30:00", "timeZone": "America/New_York"},
    "attendees": [{"email": "jane@acme.com"}]
  }' \
  "https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=all"
```

**Log the interaction:**
```sql
INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at)
VALUES (?, 'meeting', 'outbound', ?, 'Scheduled via Software of You', ?);
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('contact', ?, 'meeting_scheduled', json_object('title', ?, 'date', ?));
```

## "with <name>" View

When the user says `/calendar with Jane`:
1. Look up Jane's email from contacts
2. Search calendar events where Jane is an attendee or linked contact
3. Show past and upcoming meetings with Jane, including interaction notes

## Availability Check

When the user asks about free time:
1. Fetch today's/this week's events
2. Calculate gaps between events
3. Present available time slots: "You're free today: 10-11:30 AM, 2:30-5 PM"
