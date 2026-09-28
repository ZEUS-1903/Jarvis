"""Audition voices: hear several voices/blends say the same line.

    uv run python -m app.voice wake-setup     # download the "hey jarvis" model (once)
    uv run python -m app.voice list
    uv run python -m app.voice audition "Good evening. It's 56 degrees and cloudy." \\
        af_heart am_michael "am_michael:60,bm_george:40"

Writes voice_samples/<voice>.wav and plays each one (macOS `afplay`).
"""
import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import get_settings
from app.voice.tts import KokoroTTS


async def main(args: list[str]) -> None:
    settings = get_settings()
    tts = KokoroTTS(settings.tts_model_path, settings.tts_voices_path,
                    default_voice=settings.tts_voice, speed=settings.tts_speed)
    if args[:1] == ["wake-setup"]:
        from openwakeword.utils import download_models

        download_models([settings.wake_model])  # plus the shared feature/VAD models
        print(f"Downloaded wake word model '{settings.wake_model}'.")
        return
    if args[:1] == ["list"]:
        print("\n".join(await tts.list_voices()))
        return
    if len(args) < 3 or args[0] != "audition":
        sys.exit(__doc__)
    text, specs = args[1], args[2:]
    out_dir = Path("voice_samples")
    out_dir.mkdir(exist_ok=True)
    for spec in specs:
        path = out_dir / (re.sub(r"[^\w.-]+", "_", spec) + ".wav")
        path.write_bytes(await tts.synthesize(text, spec))
        print(f"{spec:40} -> {path}")
        if shutil.which("afplay"):
            subprocess.run(["afplay", str(path)])


asyncio.run(main(sys.argv[1:]))
