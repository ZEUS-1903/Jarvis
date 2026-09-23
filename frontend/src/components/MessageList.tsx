import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { ToolTrace } from "./ToolTrace";

export function MessageList({ messages, thinking }: { messages: ChatMessage[]; thinking: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, thinking]);

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
