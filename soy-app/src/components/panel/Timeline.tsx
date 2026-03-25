interface TimelineItem {
  id?: number;
  type?: string;
  subject?: string;
  summary?: string;
  occurred_at?: string;
  action?: string;
  details?: string;
  created_at?: string;
}

interface TimelineProps {
  items: TimelineItem[];
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function Timeline({ items }: TimelineProps) {
  if (!items.length) {
    return <p className="text-sm text-zinc-400 py-3 text-center">No activity yet</p>;
  }

  return (
    <div className="space-y-0.5">
      {items.map((item, i) => {
        const date = item.occurred_at || item.created_at;
        const title = item.subject || item.action || item.type || "Activity";
        const desc = item.summary || item.details;
        return (
          <div key={item.id ?? i} className="flex gap-3 py-2 px-1">
            <div className="flex flex-col items-center pt-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
              {i < items.length - 1 && <div className="w-px flex-1 bg-zinc-100 mt-1" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm text-zinc-900 truncate">{title}</p>
                <span className="text-xs text-zinc-400 shrink-0">{formatDate(date)}</span>
              </div>
              {desc && <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{desc}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
