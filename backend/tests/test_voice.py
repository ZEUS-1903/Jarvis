import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.voice.speech_text import to_speakable
from app.voice.tts import KokoroTTS, TTSUnavailable, parse_voice_spec, to_wav
from tests.fakes import FakeLLM, make_test_app


# ---- speech text cleanup -------------------------------------------------
@pytest.mark.parametrize(
    "screen, spoken",
    [
        ("It's **56°F** and cloudy.", "It's 56 degrees and cloudy."),
        ("Rain chance: 79% ☔️", "Rain chance: 79 percent"),
        ("See [the radar](https://x.com/r) now", "See the radar now"),
        ("Wind 13 mph", "Wind 13 miles per hour"),
        ("Current conditions:\n- Drizzle\n- 95% humidity", "Current conditions: Drizzle. 95 percent humidity"),
        ("🌧️🌧️", ""),
        ("Done.\nNext line", "Done. Next line"),
        ("It's cloudy 🌧️.", "It's cloudy."),
    ],
)
def test_to_speakable(screen, spoken):
    assert to_speakable(screen) == spoken


# ---- voice specs & wav -----------------------------------------------------
def test_parse_single_voice():
    assert parse_voice_spec("af_heart") == [("af_heart", 1.0)]


def test_parse_blend_normalizes_weights():
    assert parse_voice_spec("a:3, b:1") == [("a", 0.75), ("b", 0.25)]


@pytest.mark.parametrize("bad", ["", "a:x", "a:-1", ","])
def test_parse_rejects_bad_specs(bad):
    with pytest.raises(ValueError):
        parse_voice_spec(bad)


def test_to_wav_is_valid_16bit_mono():
    data = to_wav(np.array([0.0, 0.5, -1.5], dtype=np.float32), 24000)
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 24000, 3)


# ---- Kokoro engine (with a fake Kokoro object; no model files needed) -----
class FakeKokoro:
    def __init__(self):
        self.styles = {"a": np.ones(4, np.float32), "b": np.zeros(4, np.float32)}
        self.last_voice = None

    def get_voices(self):
        return list(self.styles)

    def get_voice_style(self, name):
        return self.styles[name]

    def create(self, text, voice, speed, lang):
        self.last_voice = voice
        return np.zeros(2400, np.float32), 24000


async def test_missing_model_files_give_setup_hint(tmp_path):
    tts = KokoroTTS(str(tmp_path / "m.onnx"), str(tmp_path / "v.bin"), default_voice="a")
    with pytest.raises(TTSUnavailable, match="Voice setup"):
        await tts.synthesize("hi")


async def test_blend_is_weighted_average_of_styles():
    tts = KokoroTTS("m", "v", default_voice="a:25,b:75")
    tts._kokoro = fake = FakeKokoro()
    wav = await tts.synthesize("hi")
    assert np.allclose(fake.last_voice, 0.25)  # 0.25*ones + 0.75*zeros
    assert wav[:4] == b"RIFF"


async def test_unknown_voice_rejected():
    tts = KokoroTTS("m", "v", default_voice="a")
    tts._kokoro = FakeKokoro()
    with pytest.raises(ValueError, match="unknown voice"):
        await tts.synthesize("hi", "zz_nobody")


# ---- API -------------------------------------------------------------------
class FakeTTS:
    default_voice = "af_heart"

    def __init__(self, error=None):
        self.error, self.spoken = error, []

    async def list_voices(self):
        if self.error:
            raise self.error
        return ["af_heart", "am_michael"]

    async def synthesize(self, text, voice=None):
        if self.error:
            raise self.error
        self.spoken.append((text, voice))
        return b"RIFFfake"


def test_speak_returns_wav_of_cleaned_text():
    tts = FakeTTS()
    client = TestClient(make_test_app(llm=FakeLLM(), tts=tts))
    r = client.post("/api/voice/speak", json={"text": "It's **56°F** 🌧️"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert tts.spoken == [("It's 56 degrees", None)]


def test_speak_not_set_up_is_503_with_hint():
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS(TTSUnavailable("download them"))))
    r = client.post("/api/voice/speak", json={"text": "hi"})
    assert r.status_code == 503 and "download" in r.json()["detail"]


def test_speak_bad_voice_is_422():
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS(ValueError("unknown voice(s): x"))))
    assert client.post("/api/voice/speak", json={"text": "hi", "voice": "x"}).status_code == 422


def test_voices_endpoint():
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS()))
    assert client.get("/api/voice/voices").json() == {"default": "af_heart",
                                                       "voices": ["af_heart", "am_michael"]}


# ---- speech-to-text ----------------------------------------------------------
from app.voice.stt import AudioDecodeError, FasterWhisperSTT, STTUnavailable, Transcript  # noqa: E402


class FakeSTT:
    def __init__(self, text="what time is it", error=None):
        self.text, self.error, self.received = text, error, []

    async def transcribe(self, audio):
        if self.error:
            raise self.error
        self.received.append(audio)
        return Transcript(text=self.text, audio_s=1.5)


def test_transcribe_returns_text():
    stt = FakeSTT()
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS(), stt=stt))
    r = client.post("/api/voice/transcribe", content=b"\x1aE\xdf\xa3webm",
                    headers={"Content-Type": "audio/webm"})
    assert r.status_code == 200
    assert r.json() == {"text": "what time is it", "audio_s": 1.5}
    assert stt.received == [b"\x1aE\xdf\xa3webm"]


@pytest.mark.parametrize("error, status", [
    (STTUnavailable("no model"), 503),
    (AudioDecodeError("could not decode audio"), 422),
])
def test_transcribe_errors(error, status):
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS(), stt=FakeSTT(error=error)))
    assert client.post("/api/voice/transcribe", content=b"x").status_code == status


def test_transcribe_rejects_empty_and_huge():
    client = TestClient(make_test_app(llm=FakeLLM(), tts=FakeTTS(), stt=FakeSTT()))
    assert client.post("/api/voice/transcribe", content=b"").status_code == 422
    assert client.post("/api/voice/transcribe", content=b"0" * (5 * 1024 * 1024 + 1)).status_code == 413


class _Seg:
    def __init__(self, text):
        self.text = text


class FakeWhisper:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, samples, **kwargs):
        self.kwargs = kwargs
        return iter([_Seg(" What time"), _Seg(" is it? ")]), None


def _wav_bytes(seconds=1.0, rate=16000):
    return to_wav(np.zeros(int(seconds * rate), np.float32), rate)


async def test_whisper_engine_decodes_and_joins_segments():
    stt = FasterWhisperSTT()
    stt._model = fake = FakeWhisper()
    result = await stt.transcribe(_wav_bytes(2.0))
    assert result.text == "What time is it?"
    assert abs(result.audio_s - 2.0) < 0.05
    assert fake.kwargs["vad_filter"] is True and fake.kwargs["language"] == "en"


async def test_whisper_engine_rejects_garbage_audio():
    stt = FasterWhisperSTT()
    stt._model = FakeWhisper()
    with pytest.raises(AudioDecodeError):
        await stt.transcribe(b"definitely not audio")


# ---- wake word WebSocket -----------------------------------------------------
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.voice.wake import FRAME, WakeUnavailable  # noqa: E402


class FakeDetector:
    """Scores 0.9 for frames whose samples are loud, 0 otherwise."""
    def __init__(self):
        self.resets = 0

    def score(self, frames):
        return 0.9 if np.abs(frames).max() > 10000 else 0.0

    def reset(self):
        self.resets += 1


def pcm(loud: bool, frames=1) -> bytes:
    value = 20000 if loud else 0
    return np.full(FRAME * frames, value, dtype="<i2").tobytes()


def test_wake_socket_detects_and_cools_down():
    detector = FakeDetector()
    client = TestClient(make_test_app(wake_factory=lambda: detector))
    with client.websocket_connect("/api/voice/wake") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(pcm(False, 3))
        ws.send_bytes(pcm(True)[:1000])      # partial frame: buffered, not scored yet
        ws.send_bytes(pcm(True)[1000:])      # completes the frame
        assert ws.receive_json() == {"type": "wake", "score": 0.9}
        ws.send_bytes(pcm(True, 2))          # within cooldown: no second event
        ws.send_text("ping")                 # text frames are ignored
    assert detector.resets == 1


def test_wake_socket_reports_missing_model():
    def broken():
        raise WakeUnavailable("run wake-setup")
    client = TestClient(make_test_app(wake_factory=broken))
    with client.websocket_connect("/api/voice/wake") as ws:
        assert ws.receive_json() == {"type": "error", "message": "run wake-setup"}


def test_wake_socket_rejects_foreign_origin():
    client = TestClient(make_test_app(wake_factory=FakeDetector))
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/voice/wake", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert exc.value.code == 1008


def test_wake_socket_allows_jarvis_origin():
    client = TestClient(make_test_app(wake_factory=FakeDetector))
    with client.websocket_connect("/api/voice/wake", headers={"origin": "http://localhost:5173"}) as ws:
        assert ws.receive_json()["type"] == "ready"


def test_real_detector_without_model_files_gives_setup_hint():
    from app.voice.wake import OpenWakeWordDetector
    with pytest.raises(WakeUnavailable, match="wake-setup"):
        OpenWakeWordDetector("hey_jarvis")  # model files aren't downloaded in CI/sandbox
