import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.voice.speech_text import to_speakable
from app.voice.tts import TTSUnavailable

router = APIRouter(prefix="/voice")
logger = logging.getLogger("jarvis.voice")


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
