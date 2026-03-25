import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { StatGrid } from "./StatGrid";
import { StatCard } from "./StatCard";
import { CalendarWeek } from "./CalendarWeek";
import { ContactList } from "./ContactList";
import { Timeline } from "./Timeline";
import { Card } from "../shared/Card";
import { Badge } from "../shared/Badge";
import { Users, Mail, Calendar, Bell } from "lucide-react";

/* eslint-disable @typescript-eslint/no-explicit-any */

export function Dashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("dashboard")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;
  if (!data) return <p className="text-sm text-zinc-400 py-8 text-center">No data available</p>;

  const nudgeTotal = Array.isArray(data.nudges)
    ? data.nudges.reduce((s: number, n: any) => s + (n.count ?? 0), 0)
    : 0;

  return (
    <div className="space-y-5">
      {/* Stats */}
      <StatGrid>
        <StatCard label="Contacts" value={data.contacts?.total ?? 0} icon={Users} />
        <StatCard label="Unread emails" value={data.emails?.unread_count ?? 0} icon={Mail} />
        <StatCard
          label="Meetings today"
          value={Array.isArray(data.calendar) ? data.calendar.length : 0}
          icon={Calendar}
        />
        <StatCard label="Nudges" value={nudgeTotal} icon={Bell} />
      </StatGrid>

      {/* Today's schedule */}
      {Array.isArray(data.calendar) && data.calendar.length > 0 && (
        <Card>
          <p className="text-xs font-medium text-zinc-500 mb-2">Today &amp; tomorrow</p>
          <CalendarWeek events={data.calendar} />
        </Card>
      )}

      {/* Follow-ups / overdue */}
      {Array.isArray(data.follow_ups) && data.follow_ups.length > 0 && (
        <Card>
          <p className="text-xs font-medium text-zinc-500 mb-2">Pending follow-ups</p>
          <div className="divide-y divide-zinc-100">
            {data.follow_ups.slice(0, 5).map((f: any) => (
              <div key={f.id} className="flex items-start justify-between gap-2 py-2">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-zinc-900 truncate">{f.contact_name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{f.reason}</p>
                </div>
                {f.due_date && (
                  <Badge variant={new Date(f.due_date) < new Date() ? "urgent" : "soon"}>
                    {new Date(f.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent contacts */}
      {Array.isArray(data.contacts?.recent) && data.contacts.recent.length > 0 && (
        <Card>
          <p className="text-xs font-medium text-zinc-500 mb-2">Recent contacts</p>
          <ContactList contacts={data.contacts.recent} />
        </Card>
      )}

      {/* Recent activity */}
      {Array.isArray(data.recent_activity) && data.recent_activity.length > 0 && (
        <Card>
          <p className="text-xs font-medium text-zinc-500 mb-2">Recent activity</p>
          <Timeline items={data.recent_activity} />
        </Card>
      )}
    </div>
  );
}
