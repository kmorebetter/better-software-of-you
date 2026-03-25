import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { CalendarWeek } from "./CalendarWeek";

/* eslint-disable @typescript-eslint/no-explicit-any */

export function CalendarPanel() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("calendar")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-zinc-700">This week</h3>
      <CalendarWeek events={data?.events ?? []} />
    </div>
  );
}
