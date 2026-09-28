"""Text-to-speech engines. The API talks to the TTSEngine interface, so tests
use a fake and a different engine (Piper, a cloud API...) could be swapped in."""
import asyncio
import io
import logging
import time
import wave
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger("jarvis.tts")


class TTSUnavailable(Exception):
    """TTS isn't set up (e.g. model files missing). Message tells the user how to fix it."""


class TTSEngine(Protocol):
    default_voice: str

    async def list_voices(self) -> list[str]: ...
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Return a complete WAV file."""
        ...


def parse_voice_spec(spec: str) -> list[tuple[str, float]]:
    """ "am_michael:60,bm_george:40" -> [("am_michael", 0.6), ("bm_george", 0.4)].

    Weights are normalized to sum to 1, so "a:3,b:1" works too. A bare name
    means 100% that voice.
    """
    parts = []
    for item in spec.split(","):
        name, _, weight = item.strip().partition(":")
        if not name:
            continue
        try:
            w = float(weight) if weight else 1.0
        except ValueError:
            raise ValueError(f"bad weight in voice spec: {item!r}")
        if w <= 0:
            raise ValueError(f"voice weight must be positive: {item!r}")
        parts.append((name, w))
    if not parts:
        raise ValueError("empty voice spec")
    total = sum(w for _, w in parts)
    return [(name, w / total) for name, w in parts]


def to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """float32 samples in [-1, 1] -> 16-bit mono WAV bytes (playable by any browser)."""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


class KokoroTTS:
    def __init__(self, model_path: str, voices_path: str, default_voice: str,
                 speed: float = 1.0, lang: str = "en-us") -> None:
        self._model_path = Path(model_path)
        self._voices_path = Path(voices_path)
        self.default_voice = default_voice
        self._speed = speed
        self._lang = lang
        self._kokoro = None  # loaded lazily: takes seconds and ~300 MB of RAM
        self._load_lock = asyncio.Lock()

    async def _engine(self):
        async with self._load_lock:  # two first requests shouldn't load it twice
            if self._kokoro is None:
                missing = [str(p) for p in (self._model_path, self._voices_path) if not p.exists()]
                if missing:
                    raise TTSUnavailable(
                        f"Voice model files not found: {', '.join(missing)}. "
                        "See README 'Voice setup' to download them."
                    )
                from kokoro_onnx import Kokoro  # heavy import, only when voice is used

                start = time.perf_counter()
                self._kokoro = await asyncio.to_thread(
                    Kokoro, str(self._model_path), str(self._voices_path))
                logger.info("tts.loaded", extra={
                    "duration_ms": round((time.perf_counter() - start) * 1000)})
            return self._kokoro

    def voices(self) -> list[str]:
        return sorted(self._kokoro.get_voices()) if self._kokoro else []

    async def list_voices(self) -> list[str]:
        await self._engine()
        return self.voices()

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        kokoro = await self._engine()
        spec = parse_voice_spec(voice or self.default_voice)
        known = set(kokoro.get_voices())
        unknown = [name for name, _ in spec if name not in known]
        if unknown:
            raise ValueError(f"unknown voice(s): {', '.join(unknown)}")

        # A blend is a weighted average of the voices' style vectors: the
        # "own voice" isn't any single preset.
        style = sum(kokoro.get_voice_style(name) * weight for name, weight in spec)

        start = time.perf_counter()
        # create() is CPU-heavy and synchronous. Running it in a worker thread
        # keeps the event loop free to serve other requests meanwhile.
        samples, sample_rate = await asyncio.to_thread(
            kokoro.create, text, voice=style.astype(np.float32),
            speed=self._speed, lang=self._lang)
        audio_s = len(samples) / sample_rate
        logger.info("tts.synthesized", extra={
            "chars": len(text), "voice": voice or self.default_voice,
            "audio_s": round(audio_s, 2),
            "duration_ms": round((time.perf_counter() - start) * 1000)})
        return to_wav(samples, sample_rate)
