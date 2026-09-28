import asyncio
import logging
import time

import numpy as np

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket
from pydantic import BaseModel, Field

from app.voice.speech_text import to_speakable
from app.voice.stt import AudioDecodeError, STTUnavailable
from app.config import get_settings
from app.voice.tts import TTSUnavailable
from app.voice.wake import FRAME, WakeUnavailable

router = APIRouter(prefix="/voice")
logger = logging.getLogger("jarvis.voice")

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # ~5 min of Opus; a spoken command is a few KB


@router.post("/transcribe")
async def transcribe(request: Request) -> dict:
    """Recorded speech -> text.

    The browser sends the raw recording as the request body with its own
    Content-Type (e.g. audio/webm). Simpler than a multipart form upload.
    """
    audio = await request.body()
    if not audio:
        raise HTTPException(422, "empty audio")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "recording too long")
    try:
        result = await request.app.state.stt.transcribe(audio)
    except STTUnavailable as exc:
        raise HTTPException(503, str(exc))
    except AudioDecodeError as exc:
        raise HTTPException(422, str(exc))
    return {"text": result.text, "audio_s": round(result.audio_s, 2)}


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = Field(default=None, max_length=200,
                              description="Override, e.g. 'af_heart' or 'am_michael:60,bm_george:40'")


@router.post("/speak", responses={200: {"content": {"audio/wav": {}}}})
async def speak(body: SpeakRequest, request: Request) -> Response:
    """Reply text -> spoken WAV audio in JARVIS's voice."""
    speakable = to_speakable(body.text)
    if not speakable:
        raise HTTPException(422, "nothing speakable in text")
    try:
        audio = await request.app.state.tts.synthesize(speakable, body.voice)
    except TTSUnavailable as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:  # bad voice spec / unknown voice name
        raise HTTPException(422, str(exc))
    return Response(content=audio, media_type="audio/wav")


@router.get("/voices")
async def voices(request: Request) -> dict:
    tts = request.app.state.tts
    try:
        names = await tts.list_voices()
    except TTSUnavailable as exc:
        raise HTTPException(503, str(exc))
    return {"default": tts.default_voice, "voices": names}


WAKE_COOLDOWN_S = 2.0  # ignore re-triggers right after a detection


@router.websocket("/wake")
async def wake(ws: WebSocket) -> None:
    """Stream mic audio in, get {"type": "wake"} out when "hey jarvis" is heard.

    Client -> server: binary messages of 16 kHz mono int16 little-endian PCM.
    Server -> client: JSON events {"type": "ready" | "wake" | "error", ...}.
    """
    settings = get_settings()
    # Browsers don't apply CORS to WebSockets: any site you visit could try to
    # connect to ws://localhost:8000. Only accept JARVIS's own page. (Non-browser
    # clients send no Origin header; they're local programs, so they're allowed.)
    origin = ws.headers.get("origin")
    if origin is not None and origin not in settings.allowed_origins:
        await ws.close(code=1008)  # policy violation
        logger.warning("wake.rejected_origin", extra={"origin": origin})
        return
    await ws.accept()

    try:
        # Loading the ONNX models takes a moment; keep the event loop free.
        detector = await asyncio.to_thread(ws.app.state.wake_factory)
    except WakeUnavailable as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return
    await ws.send_json({"type": "ready"})
    logger.info("wake.connected")

    pending = np.zeros(0, dtype=np.int16)
    cooldown_until = 0.0
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            break
        data = message.get("bytes")
        if not data:
            continue  # ignore text frames
        # Audio arrives in arbitrary sizes; keep leftovers until a full frame.
        pending = np.concatenate([pending, np.frombuffer(data[: len(data) // 2 * 2], dtype="<i2")])
        usable = len(pending) // FRAME * FRAME
        if usable == 0:
            continue
        frames, pending = pending[:usable], pending[usable:]
        score = await asyncio.to_thread(detector.score, frames)
        now = time.monotonic()
        if score >= settings.wake_threshold and now >= cooldown_until:
            cooldown_until = now + WAKE_COOLDOWN_S
            detector.reset()
            logger.info("wake.detected", extra={"score": round(score, 3)})
            await ws.send_json({"type": "wake", "score": round(score, 3)})
    logger.info("wake.disconnected")
