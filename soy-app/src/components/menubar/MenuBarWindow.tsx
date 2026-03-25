import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { Bell, Calendar, ChevronRight, MessageSquare } from "lucide-react";

interface NudgeCounts {
  urgent: number;
  soon: number;
  awareness: number;
}

interface NextMeeting {
  title: string;
  time: string;
  minutes_until: number;
}

interface MenuBarData {
  nudge_count: NudgeCounts;
  next_meeting?: NextMeeting;
  unread_emails: number;
}

export function MenuBarWindow() {
  const [data, setData] = useState<MenuBarData | null>(null);
  const [quickInput, setQuickInput] = useState("");

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60_000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const overview = await getPanelData("dashboard");
      setData({
        nudge_count: overview.nudge_summary ?? { urgent: 0, soon: 0, awareness: 0 },
        next_meeting: overview.today_events?.[0],
        unread_emails: overview.unread_count ?? 0,
      });
    } catch {
      // Menu bar should never surface errors — use stale data or empty state.
    }
  };

  const openMainWindow = async () => {
    const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
    const main = await WebviewWindow.getByLabel("main");
    if (main) {
      await main.show();
      await main.setFocus();
    }
  };

  const handleQuickInput = async () => {
    if (!quickInput.trim()) return;
    await openMainWindow();
    setQuickInput("");
  };

  const totalNudges = data
    ? data.nudge_count.urgent + data.nudge_count.soon + data.nudge_count.awareness
    : 0;

  return (
    <div className="h-full bg-white rounded-xl overflow-hidden flex flex-col select-none">
      {/* Drag region + header */}
      <div
        data-tauri-drag-region
        className="px-4 py-3 border-b border-zinc-100 flex items-center justify-between"
      >
        <span className="text-sm font-semibold text-zinc-700">Software of You</span>
        <button
          onClick={openMainWindow}
          className="text-xs text-zinc-400 hover:text-zinc-600 transition-colors flex items-center gap-0.5"
        >
          Open <ChevronRight size={12} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {data === null ? (
          <div className="text-xs text-zinc-400 text-center py-6">Loading...</div>
        ) : (
          <>
            {/* Nudge badges */}
            {totalNudges > 0 && (
              <div className="flex items-center gap-3">
                {data.nudge_count.urgent > 0 && (
                  <div className="flex items-center gap-1.5 text-xs">
                    <Bell size={12} className="text-red-500" />
                    <span className="text-red-600 font-medium">
                      {data.nudge_count.urgent} urgent
                    </span>
                  </div>
                )}
                {data.nudge_count.soon > 0 && (
                  <div className="flex items-center gap-1.5 text-xs">
                    <Bell size={12} className="text-amber-500" />
                    <span className="text-amber-600 font-medium">
                      {data.nudge_count.soon} soon
                    </span>
                  </div>
                )}
                {data.nudge_count.awareness > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                    {data.nudge_count.awareness} awareness
                  </div>
                )}
              </div>
            )}

            {totalNudges === 0 && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <Bell size={12} />
                <span>No nudges right now</span>
              </div>
            )}

            {/* Next meeting */}
            {data.next_meeting && (
              <div className="bg-zinc-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-zinc-400 mb-1">
                  <Calendar size={12} />
                  <span>
                    {data.next_meeting.minutes_until <= 0
                      ? "Now"
                      : data.next_meeting.minutes_until < 60
                        ? `In ${data.next_meeting.minutes_until}m`
                        : "Next meeting"}
                  </span>
                </div>
                <p className="text-sm font-medium text-zinc-800 leading-snug">
                  {data.next_meeting.title}
                </p>
                <p className="text-xs text-zinc-500 mt-0.5">{data.next_meeting.time}</p>
              </div>
            )}

            {/* Unread emails */}
            {data.unread_emails > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                <MessageSquare size={12} />
                <span>
                  {data.unread_emails} unread email{data.unread_emails !== 1 ? "s" : ""}
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Quick input */}
      <div className="px-4 py-3 border-t border-zinc-100">
        <input
          type="text"
          value={quickInput}
          onChange={(e) => setQuickInput(e.target.value)}
          placeholder="Quick note or question..."
          className="w-full px-3 py-2 rounded-lg bg-zinc-50 text-sm outline-none focus:ring-2 focus:ring-zinc-200 transition-shadow"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleQuickInput();
          }}
        />
      </div>
    </div>
  );
}
