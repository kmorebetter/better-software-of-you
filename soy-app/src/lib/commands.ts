import { invoke } from "@tauri-apps/api/core";

export async function sendMessage(message: string, conversationId?: string): Promise<string> {
  return invoke("send_message", { message, conversationId });
}

export async function getApiKeyStatus(): Promise<{ hasKey: boolean }> {
  return invoke("get_api_key_status");
}

export async function setApiKey(key: string): Promise<void> {
  return invoke("set_api_key", { key });
}
