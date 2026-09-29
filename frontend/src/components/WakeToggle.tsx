import { useEffect, useRef, useState } from "react";
import { WakeListener, type WakeState } from "../wake";

interface Props {
  isBusy: () => boolean;
  onCommand: (wav: Blob) => void;
  /** Errors and notices go to the app's message banner, not the header. */
  onNotice: (message: string) => void;
}

const LABELS: Record<WakeState, string> = {
  off: "Hey Jarvis: off",
  starting: "Starting…",
  listening: "Listening for “Hey Jarvis”",
  capturing: "I'm listening…",
  error: "Hey Jarvis: off",
};

/** Header switch for hands-free mode. Off by default: the mic stays on while enabled. */
export function WakeToggle({ isBusy, onCommand, onNotice }: Props) {
  const [state, setState] = useState<WakeState>("off");
  const listener = useRef<WakeListener | null>(null);
  // Keep the latest callbacks without restarting the listener on every render.
  const latest = useRef({ isBusy, onCommand, onNotice });
  latest.current = { isBusy, onCommand, onNotice };

  useEffect(() => () => listener.current?.stop(), []); // mic off when leaving the page

  function toggle() {
    if (listener.current) {
      listener.current.stop();
      listener.current = null;
      return;
    }
    listener.current = new WakeListener({
      onState: (s, detail) => {
        setState(s);
        if (detail) latest.current.onNotice(detail);
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
      <button className={`ghost wake-btn wake-${state}`} onClick={toggle} aria-pressed={on}>
        <span className="wake-dot" />
        {LABELS[state]}
      </button>
    </span>
  );
}
