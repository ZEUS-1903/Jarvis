// AudioWorklet: runs on the browser's audio thread, gets the mic in 128-sample
// blocks at the device rate (usually 48 kHz), and emits 80 ms chunks of 16 kHz
// mono int16 PCM, the format the wake word model expects.
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000; // `sampleRate` is a global in worklet scope
    this.pos = 0;                     // fractional read position for resampling
    this.chunk = new Int16Array(1280);
    this.filled = 0;
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input) return true;
    // Linear-interpolation resampling to 16 kHz.
    while (this.pos < input.length - 1) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const s = input[i] * (1 - frac) + input[i + 1] * frac;
      this.chunk[this.filled++] = Math.max(-1, Math.min(1, s)) * 32767;
      if (this.filled === this.chunk.length) {
        this.port.postMessage(this.chunk.buffer, [this.chunk.buffer]); // transfer, no copy
        this.chunk = new Int16Array(1280);
        this.filled = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= input.length - 1;
    return true; // keep the processor alive
  }
}

registerProcessor("pcm-processor", PcmProcessor);
