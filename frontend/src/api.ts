import type { ChatResponse } from "./types";

/** An API failure with the HTTP status, so the UI can react (e.g. 404 = conversation gone). */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function sendMessage(message: string, conversationId: string | null): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
  } catch {
    throw new ApiError(0, "Can't reach the Jarvis backend. Is it running on port 8000?");
  }
  if (!res.ok) {
    // FastAPI errors look like {"detail": "..."} (or a list for validation errors).
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (HTTP ${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    return (await fetch("/api/health")).ok;
  } catch {
    return false;
  }
}

/** Ask the backend to speak `text` in JARVIS's voice. Returns WAV audio. */
export async function speak(text: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new ApiError(0, "Can't reach the Jarvis backend.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, typeof body?.detail === "string" ? body.detail : `Speech failed (HTTP ${res.status})`);
  }
  return res.blob();
}
