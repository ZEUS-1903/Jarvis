/**
 * "Hey Jarvis" hands-free listening.
 *
 * mic -> AudioWorklet (16 kHz int16, 80 ms chunks) -> WebSocket -> backend wake model
 * On {"type":"wake"}: play a chime, record the command from the same audio
 * stream, stop after ~1 s of silence, and hand a WAV file to the app.
 */
export type WakeState = "off" | "starting" | "listening" | "capturing" | "error";

interface Options {
  onState: (s: WakeState, detail?: string) => void;
  onCommand: (wav: Blob) => void;
  /** True while JARVIS is thinking or speaking: wake events are ignored then. */
  isBusy: () => boolean;
}

const RATE = 16000;
const CHUNK_MS = 80;
const END_SILENCE_MS = 900;   // this much quiet after speech = end of command
const NO_SPEECH_MS = 4000;    // gave up waiting for the command to start
const MAX_COMMAND_MS = 12000;
const IGNORE_START_MS = 240;  // skip the chime itself

export class WakeListener {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private state: WakeState = "off";
  private noiseFloor = 0.01;
  private capture: { chunks: Int16Array[]; startedAt: number; speech: boolean; silentMs: number } | null = null;

  constructor(private opts: Options) {}

  async start(): Promise<void> {
    this.setState("starting");
    try {
      // Browser noise suppression/echo cancellation help avoid hearing our own voice.
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      this.fail("Microphone access was blocked.");
      return;
    }
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule("/pcm-worklet.js");
    const source = this.ctx.createMediaStreamSource(this.stream);
    const worklet = new AudioWorkletNode(this.ctx, "pcm-processor");
    worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => this.onChunk(new Int16Array(e.data));
    source.connect(worklet); // not connected to the speakers: we only analyse

    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/api/voice/wake`);
    this.ws.binaryType = "arraybuffer";
    this.ws.onmessage = (e) => this.onEvent(JSON.parse(e.data));
    this.ws.onclose = () => {
      if (this.state !== "off" && this.state !== "error") this.fail("Lost connection to the wake word service.");
    };
  }

  stop(): void {
    this.state = "off";
    this.ws?.close();
    this.stream?.getTracks().forEach((t) => t.stop()); // mic off, orange dot gone
    this.ctx?.close();
    this.ws = null;
    this.stream = null;
    this.ctx = null;
    this.capture = null;
    this.opts.onState("off");
  }

  private setState(s: WakeState, detail?: string) {
    this.state = s;
    this.opts.onState(s, detail);
  }

  private fail(message: string) {
    this.stop();
    this.setState("error", message);
  }

  private onEvent(event: { type: string; message?: string }) {
    if (event.type === "ready") this.setState("listening");
    else if (event.type === "error") this.fail(event.message ?? "Wake word error");
    else if (event.type === "wake" && this.state === "listening" && !this.opts.isBusy()) {
      this.capture = { chunks: [], startedAt: performance.now(), speech: false, silentMs: 0 };
      this.chime();
      this.setState("capturing");
    }
  }

  private onChunk(chunk: Int16Array<ArrayBuffer>) {
    const level = rms(chunk);
    if (!this.capture) {
      // Idle: keep a running estimate of background noise, and stream to the model.
      this.noiseFloor = 0.95 * this.noiseFloor + 0.05 * level;
      if (this.ws?.readyState === WebSocket.OPEN && !this.opts.isBusy()) this.ws.send(chunk.buffer);
      return;
    }
    // Capturing the command: simple energy-based end-of-speech detection.
    const c = this.capture;
    c.chunks.push(chunk);
    const elapsed = performance.now() - c.startedAt;
    const threshold = Math.max(0.015, this.noiseFloor * 3);
    if (elapsed > IGNORE_START_MS && level > threshold) {
      c.speech = true;
      c.silentMs = 0;
    } else if (c.speech) {
      c.silentMs += CHUNK_MS;
    }
    if ((c.speech && c.silentMs >= END_SILENCE_MS) || elapsed > MAX_COMMAND_MS) {
      this.capture = null;
      this.setState("listening");
      this.opts.onCommand(toWav(c.chunks));
    } else if (!c.speech && elapsed > NO_SPEECH_MS) {
      this.capture = null;
      this.setState("listening", "I didn't hear a command.");
    }
  }

  private chime() {
    if (!this.ctx) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.18);
    osc.connect(gain).connect(this.ctx.destination);
    osc.start();
    osc.stop(this.ctx.currentTime + 0.18);
  }
}

function rms(chunk: Int16Array): number {
  let sum = 0;
  for (let i = 0; i < chunk.length; i++) sum += (chunk[i] / 32768) ** 2;
  return Math.sqrt(sum / chunk.length);
}

/** 16 kHz mono int16 chunks -> a WAV file (44-byte header + samples). */
function toWav(chunks: Int16Array[]): Blob {
  const samples = chunks.reduce((n, c) => n + c.length, 0);
  const buf = new ArrayBuffer(44 + samples * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + samples * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, RATE, true); v.setUint32(28, RATE * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples * 2, true);
  let offset = 44;
  for (const c of chunks) {
    new Int16Array(buf, offset, c.length).set(c);
    offset += c.length * 2;
  }
  return new Blob([buf], { type: "audio/wav" });
}
