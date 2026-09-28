import { speak } from "./api";

// Only one thing may talk at a time (a 🔊 click, or an automatic voice reply).
let stopCurrent: (() => void) | null = null;
let speaking = false;

/** True from the moment a reply is requested until it finishes playing. */
export function isSpeaking(): boolean {
  return speaking;
}

export function stopSpeaking(): void {
  stopCurrent?.();
}

export type SpeechState = "loading" | "playing" | "idle";

/**
 * Fetch JARVIS's voice for `text` and play it.
 *
 * Pass an <audio> element created during a click/tap when you can: browsers
 * (Safari especially) only allow sound that traces back to a user gesture, and
 * speech arrives a few seconds after the click.
 */
export async function playSpeech(
  text: string,
  audio: HTMLAudioElement = new Audio(),
  onState: (s: SpeechState) => void = () => {},
): Promise<void> {
  stopSpeaking();
  let url: string | null = null;
  let cancelled = false;
  const finish = () => {
    speaking = false;
    if (url) URL.revokeObjectURL(url);
    if (stopCurrent === stop) stopCurrent = null;
    onState("idle");
  };
  const stop = () => {
    cancelled = true;
    audio.pause();
    finish();
  };
  stopCurrent = stop;
  speaking = true;
  onState("loading");
  try {
    const blob = await speak(text);
    if (cancelled) return;
    url = URL.createObjectURL(blob);
    audio.src = url;
    audio.onended = finish;
    await audio.play();
    onState("playing");
  } catch (e) {
    finish();
    throw e;
  }
}
