import { useState } from "react";
import { speak } from "../api";

// Only one reply should talk at a time: remember how to stop the current one.
let stopCurrent: (() => void) | null = null;

type State = "idle" | "loading" | "playing";

export function SpeakButton({ text }: { text: string }) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    if (state !== "idle") {
      stopCurrent?.();
      return;
    }
    stopCurrent?.();
    setError(null);

    // Create the <audio> element *inside* the click handler. Browsers only let
    // audio start in response to a user gesture; creating it now "claims" that
    // permission even though the sound arrives a moment later.
    const audio = new Audio();
    let url: string | null = null;
    let cancelled = false;
    const finish = () => {
      if (url) URL.revokeObjectURL(url); // free the blob's memory
      if (stopCurrent === stop) stopCurrent = null;
      setState("idle");
    };
    const stop = () => {
      cancelled = true;
      audio.pause();
      finish();
    };
    stopCurrent = stop;
    setState("loading");

    try {
      const blob = await speak(text);
      if (cancelled) return;
      url = URL.createObjectURL(blob);
      audio.src = url;
      audio.onended = finish;
      await audio.play();
      setState("playing");
    } catch (e) {
      finish();
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const label = state === "loading" ? "…" : state === "playing" ? "■" : "🔊";
  return (
    <div className="speak">
      <button
        className="speak-btn"
        onClick={onClick}
        title={state === "idle" ? "Read aloud" : "Stop"}
        aria-label={state === "idle" ? "Read aloud" : "Stop"}
      >
        {label}
      </button>
      {error && <span className="speak-error">{error}</span>}
    </div>
  );
}
