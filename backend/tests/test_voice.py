import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.voice.speech_text import to_speakable
from app.voice.tts import KokoroTTS, TTSUnavailable, parse_voice_spec, to_wav
from tests.fakes import FakeLLM


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
    client = TestClient(create_app(llm=FakeLLM(), tts=tts))
    r = client.post("/api/voice/speak", json={"text": "It's **56°F** 🌧️"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert tts.spoken == [("It's 56 degrees", None)]


def test_speak_not_set_up_is_503_with_hint():
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(TTSUnavailable("download them"))))
    r = client.post("/api/voice/speak", json={"text": "hi"})
    assert r.status_code == 503 and "download" in r.json()["detail"]


def test_speak_bad_voice_is_422():
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS(ValueError("unknown voice(s): x"))))
    assert client.post("/api/voice/speak", json={"text": "hi", "voice": "x"}).status_code == 422


def test_voices_endpoint():
    client = TestClient(create_app(llm=FakeLLM(), tts=FakeTTS()))
    assert client.get("/api/voice/voices").json() == {"default": "af_heart",
                                                       "voices": ["af_heart", "am_michael"]}
