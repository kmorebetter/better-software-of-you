import { invoke } from "@tauri-apps/api/core";

export async function sendMessage(message: string, conversationId?: number): Promise<string> {
  return invoke("send_message", { message, conversationId });
}

export async function createConversation(): Promise<{ id: number }> {
  return invoke("create_conversation");
}

export async function getRecentConversation(): Promise<{
  conversation: { id: number; title: string; created_at: string } | null;
  messages: Array<{
    role: string;
    content: string;
    panel_hint?: string;
    created_at: string;
  }>;
}> {
  return invoke("get_recent_conversation");
}

export async function saveMessage(
  conversationId: number,
  role: string,
  content: string,
  panelHint?: string,
): Promise<{ id: number }> {
  return invoke("save_message", { conversationId, role, content, panelHint });
}

export async function getApiKeyStatus(): Promise<{ hasKey: boolean }> {
  return invoke("get_api_key_status");
}

export async function setApiKey(key: string): Promise<void> {
  return invoke("set_api_key", { key });
}

export async function getPanelData(panelType: string, entityId?: number): Promise<any> {
  return invoke("get_panel_data", { panelType, entityId });
}

export async function getOnboardingState(): Promise<{
  stage: string;
  contactCount: number;
  hasProfile: boolean;
}> {
  return invoke("get_onboarding_state");
}

export async function getGoogleStatus(): Promise<{
  connected: boolean;
  email: string | null;
}> {
  return invoke("get_google_status");
}

export async function connectGoogle(): Promise<{
  status: string;
  message: string;
}> {
  return invoke("connect_google");
}

export async function disconnectGoogle(): Promise<{
  status: string;
  message: string;
}> {
  return invoke("disconnect_google");
}
