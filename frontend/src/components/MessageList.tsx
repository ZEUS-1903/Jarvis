import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { ToolTrace } from "./ToolTrace";

export function MessageList({ messages, thinking }: { messages: ChatMessage[]; thinking: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  // Braces matter: without them the arrow would *return* scrollIntoView()'s result,
  // and React treats any returned value as a cleanup function. Newer browsers
  // return a Promise there, which crashed the app ("destroy is not a function").
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  return (
    <div className="messages">
      {messages.length === 0 && (
        <div className="empty">
          <h2>How can I help?</h2>
          <p>Try “What time is it in Tokyo?” or “What's 18% tip on $86.40?”</p>
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`msg ${m.role}`}>
          {m.role === "assistant" && <ToolTrace tools={m.tools} />}
          <div className="bubble">{m.content}</div>
        </div>
      ))}
      {thinking && (
        <div className="msg assistant">
          <div className="bubble thinking"><span /><span /><span /></div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
