import { PanelHint } from "../../lib/types";
import { EmptyState } from "./EmptyState";
import { Dashboard } from "./Dashboard";
import { EntityPage } from "./EntityPage";
import { NudgeFeed } from "./NudgeFeed";
import { CommitmentPanel } from "./CommitmentPanel";
import { CalendarPanel } from "./CalendarPanel";
import { EmailPanel } from "./EmailPanel";
import { MeetingPrep } from "./MeetingPrep";
import { TimelinePanel } from "./TimelinePanel";
import { SettingsPanel } from "./SettingsPanel";

interface PanelRouterProps {
  panel: PanelHint;
}

export function PanelRouter({ panel }: PanelRouterProps) {
  switch (panel.type) {
    case "dashboard":
      return <Dashboard />;
    case "contact":
      return <EntityPage entityId={panel.entityId} />;
    case "nudges":
      return <NudgeFeed />;
    case "commitments":
      return <CommitmentPanel />;
    case "calendar":
      return <CalendarPanel />;
    case "email":
      return <EmailPanel />;
    case "meeting-prep":
      return <MeetingPrep entityId={panel.entityId} />;
    case "timeline":
      return <TimelinePanel />;
    case "settings":
      return <SettingsPanel />;
    default:
      return <EmptyState message={`Unknown panel: ${panel.type}`} />;
  }
}
