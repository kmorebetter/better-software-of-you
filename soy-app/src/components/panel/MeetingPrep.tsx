import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { Card } from "../shared/Card";
import { Avatar } from "../shared/Avatar";
import { CalendarClock } from "lucide-react";

interface MeetingPrepData {
  event?: {
    title?: string;
    start_time?: string;
    location?: string;
    minutes_until?: number;
  };
  contacts?: Array<{
    name?: string;
    company?: string;
    days_silent?: number;
    email_count?: number;
  }>;
  open_commitments?: Array<{ description?: string; urgency?: string }>;
  recent_emails?: Array<{ subject?: string; direction?: string }>;
  recent_interactions?: Array<{ type?: string; subject?: string }>;
}

interface MeetingPrepProps {
  entityId?: number;
}

function formatTime(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function MeetingPrep({ entityId }: MeetingPrepProps) {
  const [data, setData] = useState<MeetingPrepData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("meeting-prep", entityId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [entityId]);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;

  if (!data?.event) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-zinc-400">
        <CalendarClock size={20} />
        <p className="text-sm">No upcoming meetings</p>
      </div>
    );
  }

  const { event, contacts, open_commitments, recent_emails } = data;

  return (
    <div className="space-y-4">
      {/* Meeting header */}
      <div>
        <h3 className="text-base font-semibold text-zinc-900">{event.title}</h3>
        <p className="text-xs text-zinc-500 mt-0.5">
          {formatTime(event.start_time)}
          {event.location ? ` \u00B7 ${event.location}` : ""}
          {event.minutes_until != null && event.minutes_until > 0
            ? ` \u00B7 in ${Math.round(event.minutes_until)}m`
            : ""}
        </p>
      </div>

      {/* Attendee briefs */}
      {contacts && contacts.length > 0 && (
        <Section title="Attendees">
          {contacts.map((c, i) => (
            <div key={i} className="flex items-center gap-2.5 py-1.5">
              <Avatar name={c.name ?? "?"} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-zinc-900 truncate">{c.name}</p>
                <p className="text-xs text-zinc-500">
                  {c.company ?? ""}
                  {c.days_silent != null ? ` \u00B7 ${c.days_silent}d silent` : ""}
                </p>
              </div>
            </div>
          ))}
        </Section>
      )}

      {/* Open commitments */}
      {open_commitments && open_commitments.length > 0 && (
        <Section title="Open threads">
          {open_commitments.slice(0, 5).map((c, i) => (
            <p key={i} className="text-sm text-zinc-700 py-0.5">
              \u2022 {c.description}
            </p>
          ))}
        </Section>
      )}

      {/* Recent emails */}
      {recent_emails && recent_emails.length > 0 && (
        <Section title="Recent emails">
          {recent_emails.slice(0, 4).map((e, i) => (
            <p key={i} className="text-sm text-zinc-700 py-0.5 truncate">
              {e.direction === "inbound" ? "\u2199" : "\u2197"} {e.subject}
            </p>
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <p className="text-xs font-medium text-zinc-500 mb-2">{title}</p>
      {children}
    </Card>
  );
}
