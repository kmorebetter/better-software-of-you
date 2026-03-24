export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  panelHint?: PanelHint;
  timestamp: string;
  isStreaming?: boolean;
}

export interface PanelHint {
  type: "contact" | "dashboard" | "calendar" | "email" | "timeline" | "meeting-prep" | "nudges" | "commitments" | "settings" | "composition";
  entityId?: number;
  title?: string;
  composition?: CompositionSpec;
}

export interface CompositionSpec {
  layout: "single" | "two-column" | "stacked";
  components: ComponentSpec[];
}

export interface ComponentSpec {
  type: string;
  props: Record<string, unknown>;
}

export interface StreamEvent {
  token?: string;
  done?: boolean;
  panelHint?: PanelHint;
  error?: string;
}
