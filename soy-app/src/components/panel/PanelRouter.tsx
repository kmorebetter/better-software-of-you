import { PanelHint } from "../../lib/types";
import { EmptyState } from "./EmptyState";

interface PanelRouterProps {
  panel: PanelHint;
}

export function PanelRouter({ panel }: PanelRouterProps) {
  switch (panel.type) {
    case "dashboard":
      return <EmptyState message="Dashboard coming soon" />;
    case "contact":
      return <EmptyState message={`Contact #${panel.entityId}`} />;
    case "calendar":
      return <EmptyState message="Calendar coming soon" />;
    default:
      return <EmptyState message={`Unknown panel: ${panel.type}`} />;
  }
}
