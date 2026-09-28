"""Wake-word detection ("hey jarvis") with openWakeWord.

openWakeWord scores audio in 80 ms frames (1280 samples at 16 kHz). Each frame
gets a score from 0 to 1; above the threshold means "the phrase was just said".
The model keeps a short rolling audio buffer internally, so each WebSocket
connection gets its own detector instance.
"""
from typing import Protocol

import numpy as np

FRAME = 1280  # samples per 80 ms at 16 kHz


class WakeUnavailable(Exception):
    """openWakeWord or its model files aren't set up."""


class WakeDetector(Protocol):
    def score(self, frames: np.ndarray) -> float:
        """Highest wake score over these int16 16 kHz samples (a multiple of FRAME)."""
        ...

    def reset(self) -> None: ...


class OpenWakeWordDetector:
    def __init__(self, model_name: str = "hey_jarvis") -> None:
        try:
            from openwakeword.model import Model

            self._model = Model(wakeword_models=[model_name], inference_framework="onnx")
        except Exception as exc:
            raise WakeUnavailable(
                f"Wake word model '{model_name}' isn't available ({exc}). "
                "Download it once with: uv run python -m app.voice wake-setup"
            ) from exc
        self._name = model_name

    def score(self, frames: np.ndarray) -> float:
        best = 0.0
        for start in range(0, len(frames) - FRAME + 1, FRAME):
            scores = self._model.predict(frames[start:start + FRAME])
            best = max(best, float(scores.get(self._name, 0.0)))
        return best

    def reset(self) -> None:
        # Clears the rolling buffer so the same "hey jarvis" isn't detected twice.
        self._model.reset()
