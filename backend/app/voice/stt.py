"""Speech-to-text engines (same pattern as tts.py: an interface + a local engine)."""
import asyncio
import io
import logging
import time
from typing import Protocol

from pydantic import BaseModel

logger = logging.getLogger("jarvis.stt")


class STTUnavailable(Exception):
    """STT can't run (e.g. model download failed). Message explains how to fix it."""


class AudioDecodeError(ValueError):
    """The uploaded bytes aren't audio we can decode."""


class Transcript(BaseModel):
    text: str
    audio_s: float  # length of the speech that was sent


class STTEngine(Protocol):
    async def transcribe(self, audio: bytes) -> Transcript: ...


class FasterWhisperSTT:
    def __init__(self, model: str = "base.en", compute_type: str = "int8") -> None:
        self._model_name = model
        self._compute_type = compute_type
        self._model = None
        self._load_lock = asyncio.Lock()

    async def _engine(self):
        async with self._load_lock:
            if self._model is None:
                from faster_whisper import WhisperModel  # heavy import, only when used

                start = time.perf_counter()
                try:
                    # First call downloads the model from Hugging Face and caches it
                    # (~/.cache/huggingface); later starts load from disk.
                    self._model = await asyncio.to_thread(
                        WhisperModel, self._model_name, device="cpu",
                        compute_type=self._compute_type)
                except Exception as exc:
                    raise STTUnavailable(
                        f"Could not load Whisper model '{self._model_name}': {exc}. "
                        "The first run needs internet access to download it."
                    ) from exc
                logger.info("stt.loaded", extra={
                    "model": self._model_name,
                    "duration_ms": round((time.perf_counter() - start) * 1000)})
            return self._model

    async def transcribe(self, audio: bytes) -> Transcript:
        model = await self._engine()
        start = time.perf_counter()
        text, audio_s = await asyncio.to_thread(self._run, model, audio)
        logger.info("stt.transcribed", extra={
            "audio_s": round(audio_s, 2), "chars": len(text),
            "duration_ms": round((time.perf_counter() - start) * 1000)})
        return Transcript(text=text, audio_s=audio_s)

    @staticmethod
    def _run(model, audio: bytes) -> tuple[str, float]:
        from faster_whisper import decode_audio

        # Browsers record compressed audio (Chrome: WebM/Opus, Safari: MP4/AAC).
        # decode_audio uses PyAV (bundled FFmpeg) to turn it into the 16 kHz mono
        # samples Whisper expects.
        try:
            samples = decode_audio(io.BytesIO(audio), sampling_rate=16000)
        except Exception as exc:
            raise AudioDecodeError("could not decode audio") from exc
        segments, _info = model.transcribe(
            samples,
            language="en",
            beam_size=5,
            # Voice activity detection: skip silence. Whisper tends to invent
            # text ("Thank you.") when fed silence; VAD prevents most of that.
            vad_filter=True,
        )
        # `segments` is a lazy generator: transcription happens while we iterate.
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text, len(samples) / 16000
