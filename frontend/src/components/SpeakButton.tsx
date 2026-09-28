import { useState } from "react";
import { playSpeech, stopSpeaking, type SpeechState } from "../speech";

export function SpeakButton({ text }: { text: string }) {
  const [state, setState] = useState<SpeechState>("idle");
  const [error, setError] = useState<string | null>(null);

  function onClick() {
    if (state !== "idle") {
      stopSpeaking();
      return;
    }
    setError(null);
    // new Audio() here, inside the click handler: see playSpeech() for why.
    playSpeech(text, new Audio(), setState).catch((e) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }

  const label = state === "loading" ? "…" : state === "playing" ? "■" : "🔊";
  const title = state === "idle" ? "Read aloud" : "Stop";
  return (
    <div className="speak">
      <button className="speak-btn" onClick={onClick} title={title} aria-label={title}>
        {label}
      </button>
      {error && <span className="speak-error">{error}</span>}
    </div>
  );
}
