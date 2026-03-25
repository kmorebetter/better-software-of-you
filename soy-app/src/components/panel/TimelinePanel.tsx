import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { Timeline } from "./Timeline";

/* eslint-disable @typescript-eslint/no-explicit-any */

export function TimelinePanel() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Reuse dashboard data for activity timeline
    getPanelData("dashboard")
      .then((data: any) => setItems(data?.recent_activity ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-zinc-700">Activity timeline</h3>
      <Timeline items={items} />
    </div>
  );
}
