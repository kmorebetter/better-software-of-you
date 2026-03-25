import { CompositionSpec, ComponentSpec } from "../../lib/types";
import { StatGrid } from "./StatGrid";
import { StatCard } from "./StatCard";
import { Timeline } from "./Timeline";
import { EmailList } from "./EmailList";
import { CommitmentList } from "./CommitmentList";
import { ContactList } from "./ContactList";
import { NudgeFeed } from "./NudgeFeed";
import { CalendarWeek } from "./CalendarWeek";
import { EmptyState } from "./EmptyState";

const COMPONENT_REGISTRY: Record<string, React.ComponentType<any>> = {
  "stat-grid": StatGrid,
  "stat-card": StatCard,
  timeline: Timeline,
  "email-list": EmailList,
  "commitment-list": CommitmentList,
  "contact-list": ContactList,
  "nudge-feed": NudgeFeed,
  "calendar-week": CalendarWeek,
};

interface CompositionRendererProps {
  spec: CompositionSpec;
}

export function CompositionRenderer({ spec }: CompositionRendererProps) {
  const renderComponent = (comp: ComponentSpec, index: number) => {
    const Component = COMPONENT_REGISTRY[comp.type];
    if (!Component) {
      return (
        <EmptyState key={index} message={`Unknown component: ${comp.type}`} />
      );
    }
    return <Component key={index} {...comp.props} />;
  };

  if (spec.layout === "two-column") {
    return (
      <div className="grid grid-cols-2 gap-4">
        {spec.components.map(renderComponent)}
      </div>
    );
  }

  // Default: single or stacked
  return (
    <div className="flex flex-col gap-4">
      {spec.components.map(renderComponent)}
    </div>
  );
}
