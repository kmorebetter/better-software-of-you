import { useEffect, useState } from "react";
import { Badge } from "../shared/Badge";
import { getPanelData } from "../../lib/commands";
import { Bell } from "lucide-react";

interface NudgeItem {
  nudge_type: string;
  entity_name?: string;
  description?: string;
  days_value?: number;
  icon?: string;
}

interface NudgeData {
  urgent?: NudgeItem[];
  soon?: NudgeItem[];
  awareness?: NudgeItem[];
  counts?: { total?: number };
}

export function NudgeFeed() {
  const [data, setData] = useState<NudgeData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("nudges")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;
  }

  const total = data?.counts?.total ?? 0;
  if (!data || total === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-zinc-400">
        <Bell size={20} />
        <p className="text-sm">All clear — no nudges</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <NudgeTier label="Urgent" variant="urgent" items={data.urgent} />
      <NudgeTier label="Soon" variant="soon" items={data.soon} />
      <NudgeTier label="Awareness" variant="awareness" items={data.awareness} />
    </div>
  );
}

function NudgeTier({
  label,
  variant,
  items,
}: {
  label: string;
  variant: "urgent" | "soon" | "awareness";
  items?: NudgeItem[];
}) {
  if (!items?.length) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Badge variant={variant}>{label}</Badge>
        <span className="text-xs text-zinc-400">{items.length}</span>
      </div>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2 rounded-lg px-3 py-2 hover:bg-zinc-50">
            <span className="text-sm mt-0.5">{item.icon ?? "\u2022"}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-zinc-900">
                {item.entity_name && (
                  <span className="font-medium">{item.entity_name}: </span>
                )}
                {item.description}
              </p>
              {item.days_value != null && (
                <p className="text-xs text-zinc-500 mt-0.5">
                  {item.days_value > 0 ? `${item.days_value}d` : "Today"}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
