// Remember the open conversation across page reloads (per browser, best effort).
// The messages themselves live in Postgres; we only keep the id here.
const KEY = "jarvis.conversationId";

export function loadConversationId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null; // storage blocked (e.g. private mode)
  }
}

export function saveConversationId(id: string | null): void {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    // storage blocked: the conversation just won't survive a reload
  }
}
