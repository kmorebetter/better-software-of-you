import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { Avatar } from "../shared/Avatar";
import { Card } from "../shared/Card";
import { StatGrid } from "./StatGrid";
import { StatCard } from "./StatCard";
import { CommitmentList } from "./CommitmentList";
import { EmailList } from "./EmailList";
import { CalendarWeek } from "./CalendarWeek";
import { Timeline } from "./Timeline";
import { Mail, MessageSquare, Clock, TrendingUp } from "lucide-react";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface EntityPageProps {
  entityId?: number;
}

export function EntityPage({ entityId }: EntityPageProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (entityId == null) return;
    setLoading(true);
    getPanelData("contact", entityId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [entityId]);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;
  if (!data?.contact) return <p className="text-sm text-zinc-400 py-8 text-center">Contact not found</p>;

  const c = data.contact;
  const h = data.health ?? {};

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Avatar name={c.name ?? "?"} size="lg" />
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-zinc-900 truncate">{c.name}</h3>
          {(c.role || c.company) && (
            <p className="text-sm text-zinc-500 truncate">
              {[c.role, c.company].filter(Boolean).join(" at ")}
            </p>
          )}
        </div>
      </div>

      {/* Stats */}
      <StatGrid>
        <StatCard label="Emails" value={h.email_count ?? 0} icon={Mail} />
        <StatCard label="Interactions" value={h.interaction_count ?? 0} icon={MessageSquare} />
        <StatCard
          label="Days silent"
          value={h.days_silent ?? "\u2014"}
          icon={Clock}
          muted={h.days_silent == null}
        />
        <StatCard
          label="Depth"
          value={h.relationship_depth ?? "\u2014"}
          icon={TrendingUp}
          muted={h.relationship_depth == null}
        />
      </StatGrid>

      {/* Commitments */}
      <PanelSection title="Open commitments" items={data.commitments}>
        <CommitmentList commitments={data.commitments ?? []} />
      </PanelSection>

      {/* Emails */}
      <PanelSection title="Recent emails" items={data.emails}>
        <EmailList emails={data.emails ?? []} />
      </PanelSection>

      {/* Calendar */}
      <PanelSection title="Meetings" items={data.calendar_events}>
        <CalendarWeek events={data.calendar_events ?? []} />
      </PanelSection>

      {/* Timeline */}
      <PanelSection title="Interaction history" items={data.interactions}>
        <Timeline items={data.interactions ?? []} />
      </PanelSection>
    </div>
  );
}

function PanelSection({ title, items, children }: { title: string; items?: any[]; children: React.ReactNode }) {
  if (!items?.length) return null;
  return (
    <Card>
      <p className="text-xs font-medium text-zinc-500 mb-2">{title}</p>
      {children}
    </Card>
  );
}
