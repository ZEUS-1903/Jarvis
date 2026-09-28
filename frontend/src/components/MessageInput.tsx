import { useState, type KeyboardEvent, type ReactNode } from "react";

const MAX_CHARS = 4000; // same limit the backend enforces

export function MessageInput({ onSend, disabled, extra }: { onSend: (text: string) => void; disabled: boolean; extra?: ReactNode }) {
  const [text, setText] = useState("");

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="composer">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
        onKeyDown={onKeyDown}
        placeholder="Message Jarvis…"
        rows={1}
        autoFocus
      />
      {extra}
      <button onClick={submit} disabled={disabled || !text.trim()} aria-label="Send">↑</button>
    </div>
  );
}
