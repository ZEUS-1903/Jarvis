import { useEffect, useState } from "react";
import { ApiError, checkHealth, sendMessage } from "./api";
import { MessageInput } from "./components/MessageInput";
import { MessageList } from "./components/MessageList";
import type { ChatMessage } from "./types";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Returned by the backend on the first reply; sent back so it can find the history.
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then(setOnline);
  }, []);

  async function handleSend(text: string) {
    setError(null);
    // Optimistic update: show the user's message immediately.
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setThinking(true);
    try {
      const res = await sendMessage(text, conversationId);
      setConversationId(res.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply, tools: res.tool_calls, requestId: res.request_id },
      ]);
      setOnline(true);
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, String(e));
      if (err.status === 404) {
        // Backend restarted and lost in-memory history (expected in V1).
        setConversationId(null);
        setError("Jarvis restarted and lost this conversation. Send your message again to start fresh.");
      } else {
        setError(err.message);
        if (err.status === 0) setOnline(false);
      }
    } finally {
      setThinking(false);
    }
  }

  function newChat() {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className={`status ${online === false ? "down" : online ? "up" : ""}`} />
          Jarvis
        </div>
        <button className="ghost" onClick={newChat} disabled={thinking}>New chat</button>
      </header>
      <MessageList messages={messages} thinking={thinking} />
      {error && <div className="error" role="alert">{error}</div>}
      <MessageInput onSend={handleSend} disabled={thinking} />
    </div>
  );
}
