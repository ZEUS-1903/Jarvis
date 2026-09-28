import { useEffect, useRef, useState } from "react";
import { WakeListener, type WakeState } from "../wake";

interface Props {
  isBusy: () => boolean;
  onCommand: (wav: Blob) => void;
}

const LABELS: Record<WakeState, string> = {
  off: "Hey Jarvis: off",
  starting: "Starting…",
  listening: "Listening for “Hey Jarvis”",
  capturing: "I'm listening…",
  error: "Hey Jarvis: off",
};

/** Header switch for hands-free mode. Off by default: the mic stays on while enabled. */
export function WakeToggle({ isBusy, onCommand }: Props) {
  const [state, setState] = useState<WakeState>("off");
  const [note, setNote] = useState<string | null>(null);
  const listener = useRef<WakeListener | null>(null);
  // Keep the latest callbacks without restarting the listener on every render.
  const latest = useRef({ isBusy, onCommand });
  latest.current = { isBusy, onCommand };

  useEffect(() => () => listener.current?.stop(), []); // mic off when leaving the page

  function toggle() {
    if (listener.current) {
      listener.current.stop();
      listener.current = null;
      return;
    }
    setNote(null);
    listener.current = new WakeListener({
      onState: (s, detail) => {
        setState(s);
        setNote(detail ?? null);
        if (s === "error") listener.current = null;
      },
      onCommand: (wav) => latest.current.onCommand(wav),
      isBusy: () => latest.current.isBusy(),
    });
    listener.current.start();
  }

  const on = state === "listening" || state === "capturing" || state === "starting";
  return (
    <span className="wake">
      <button className={`ghost wake-btn ${state}`} onClick={toggle} aria-pressed={on} title={note ?? undefined}>
        <span className="wake-dot" />
        {LABELS[state]}
      </button>
      {note && <span className="wake-note">{note}</span>}
    </span>
  );
}
