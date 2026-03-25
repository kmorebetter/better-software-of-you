import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { CommitmentList } from "./CommitmentList";

/* eslint-disable @typescript-eslint/no-explicit-any */

export function CommitmentPanel() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("commitments")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-zinc-700">Commitments</h3>
        {data?.overdue_count > 0 && (
          <span className="text-xs text-red-600 font-medium">{data.overdue_count} overdue</span>
        )}
      </div>
      <CommitmentList commitments={data?.commitments ?? []} />
    </div>
  );
}
