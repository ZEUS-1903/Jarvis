import { useEffect, useRef, useState } from "react";
import { stopSpeaking } from "../speech";

const MAX_SECONDS = 30; // a command, not a dictation session

interface Props {
  disabled: boolean;
  /** Called with the recording, plus an <audio> element created during the click
   *  (so the spoken reply is allowed to play later). */
  onRecorded: (audio: Blob, player: HTMLAudioElement) => void;
  onError: (message: string) => void;
}

/** Click to start talking, click again to send. */
export function MicButton({ disabled, onRecorded, onError }: Props) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const playerRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<number | null>(null);

  // Release the microphone if the component goes away mid-recording.
  useEffect(() => {
    return () => {
      recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function start() {
    stopSpeaking(); // never record JARVIS's own voice
    let stream: MediaStream;
    try {
      // Browser asks for microphone permission the first time.
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("Microphone access was blocked. Allow it in the browser's site settings (the icon left of the address bar).");
      return;
    }
    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(stream); // Chrome: audio/webm (Opus), Safari: audio/mp4
    recorder.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop()); // turn the mic (and macOS's orange dot) off
      if (timerRef.current) window.clearInterval(timerRef.current);
      setRecording(false);
      const blob = new Blob(chunks, { type: recorder.mimeType });
      if (blob.size > 0) onRecorded(blob, playerRef.current ?? new Audio());
    };
    recorderRef.current = recorder;
    recorder.start();
    setRecording(true);
    setSeconds(0);
    const startedAt = Date.now();
    timerRef.current = window.setInterval(() => {
      const s = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(s);
      if (s >= MAX_SECONDS) stop();
    }, 250);
  }

  function stop() {
    playerRef.current = new Audio(); // created during the click: see speech.ts
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  return (
    <button
      className={`mic ${recording ? "recording" : ""}`}
      onClick={recording ? stop : start}
      disabled={disabled && !recording}
      title={recording ? "Stop and send" : "Talk to Jarvis"}
      aria-label={recording ? "Stop and send" : "Talk to Jarvis"}
    >
      {recording ? `■ ${seconds}s` : "🎤"}
    </button>
  );
}
