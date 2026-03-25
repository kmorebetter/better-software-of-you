import { Calendar } from "lucide-react";

interface CalendarEvent {
  id: number;
  title: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  all_day?: boolean | number;
}

interface CalendarWeekProps {
  events: CalendarEvent[];
}

function formatTime(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function dayLabel(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const isTomorrow = d.toDateString() === tomorrow.toDateString();
  if (isToday) return "Today";
  if (isTomorrow) return "Tomorrow";
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export function CalendarWeek({ events }: CalendarWeekProps) {
  if (!events.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-zinc-400">
        <Calendar size={20} />
        <p className="text-sm">No events this week</p>
      </div>
    );
  }

  // Group events by day
  const grouped = new Map<string, CalendarEvent[]>();
  for (const evt of events) {
    const key = evt.start_time ? new Date(evt.start_time).toDateString() : "Unknown";
    const arr = grouped.get(key) ?? [];
    arr.push(evt);
    grouped.set(key, arr);
  }

  return (
    <div className="space-y-4">
      {Array.from(grouped.entries()).map(([dayKey, dayEvents]) => (
        <div key={dayKey}>
          <p className="text-xs font-medium text-zinc-500 mb-1.5">
            {dayLabel(dayEvents[0].start_time)}
          </p>
          <div className="space-y-1">
            {dayEvents.map((evt) => (
              <div
                key={evt.id}
                className="flex items-start gap-2 rounded-lg border border-zinc-100 bg-zinc-50/50 px-3 py-2"
              >
                <div className="w-1 self-stretch rounded-full bg-blue-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-zinc-900 truncate">{evt.title}</p>
                  <p className="text-xs text-zinc-500">
                    {evt.all_day ? "All day" : formatTime(evt.start_time)}
                    {evt.location ? ` \u00B7 ${evt.location}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
