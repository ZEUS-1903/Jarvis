import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import type { ChatMessage } from "../types";
import { SpeakButton } from "./SpeakButton";
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
          {m.role === "assistant" ? (
            // react-markdown builds React elements; it never injects raw HTML
            // and strips javascript: links, so model output can't run scripts.
            <>
              <div className="bubble md"><Markdown>{m.content}</Markdown></div>
              <SpeakButton text={m.content} />
            </>
          ) : (
            <div className="bubble">{m.content}</div>
          )}
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
