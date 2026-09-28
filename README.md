# JARVIS

A personal AI assistant, built incrementally as a learning project.
Design: [docs/v1-architecture.md](docs/v1-architecture.md)

## Quick start on a Mac (from zero)

You need 3 terminal windows. Takes ~15 minutes, mostly the model download.

### 1. Install the tools (once)

```bash
# Homebrew (skip if `brew --version` already works)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install uv node ollama
```

- `uv` manages Python and backend dependencies (it downloads Python itself if needed).
- `node` runs the React frontend (Node 20.19+ or 22.12+ required by Vite).
- `ollama` runs the LLM locally, free.

### 2. Start the model — Terminal 1

```bash
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
```

Leave it running. Why the settings: on a 16 GB Mac Ollama defaults to a 4,096-token
context window; system prompt + tool schemas + history + Qwen3's reasoning can exceed
that, and Ollama then silently drops the *start* of the prompt (the system prompt).
8,192 fits comfortably; flash attention and the 8-bit KV cache keep the extra memory small.

In another tab, download the model once (~5 GB, fits a 16 GB Mac):

```bash
ollama pull qwen3:8b
ollama run qwen3:8b "say hi"   # sanity check, then Ctrl+D
```

### 3. Start the backend — Terminal 2

```bash
cd jarvis/backend
cp ../.env.example .env      # edit timezone/units if needed
uv sync                      # installs dependencies into backend/.venv
uv run pytest                # optional: all tests should pass
uv run uvicorn app.main:app --reload --port 8000
```

Check: http://localhost:8000/api/health shows `{"status":"ok"}`.
API docs: http://localhost:8000/docs

### 4. Start the frontend — Terminal 3

```bash
cd jarvis/frontend
npm install
npm run dev
```

Open **http://localhost:5173** and ask: *"What's the weather in Boston and what time is it there?"*

### Troubleshooting

| Symptom | Fix |
|---|---|
| Red dot in the UI header | Backend isn't running on port 8000 (Terminal 2). |
| "The language model is unavailable: cannot reach LLM" | Ollama isn't running (Terminal 1). |
| "HTTP 404 … model not found" | Run `ollama pull qwen3:8b`, or set `JARVIS_LLM_MODEL` in `backend/.env` to a name from `ollama list`. |
| Replies take 20s+ | Try `JARVIS_LLM_MODEL=llama3.1:8b` (pull it first) and restart the backend. |
| "Jarvis restarted and lost this conversation" | Expected in V1: history is in memory and `--reload` restarts on code changes. |
| `address already in use` | Something else uses the port; stop it or change `--port`. |

## Voice setup (text-to-speech)

JARVIS speaks with [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), a small
open-weights (Apache-2.0) voice model that runs locally. Download the model files once
(~340 MB):

```bash
cd backend
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd .. && uv sync
```

If a download 404s, get the current file names from the project's releases page.

Pick JARVIS's voice by auditioning (plays each sample on macOS):

```bash
uv run python -m app.voice list            # all voice names
uv run python -m app.voice audition "Good evening. It's 56 degrees with light drizzle." \
    af_heart am_michael bm_george "am_michael:60,bm_george:40"
```

Voice names: first letter = accent (`a` American, `b` British), second = `f`/`m`.
A blend like `am_michael:60,bm_george:40` mixes voices into one that is none of the
presets. Put your choice in `backend/.env` as `JARVIS_TTS_VOICE=...` and restart the
backend. In the chat, click 🔊 under any reply.

## Voice input (speech-to-text)

Click 🎤, speak, click again. Your speech is transcribed locally by Whisper
([faster-whisper](https://github.com/SYSTRAN/faster-whisper)), sent to JARVIS, and the
reply is spoken back automatically. The first use downloads the Whisper model
(`base.en`, ~150 MB) from Hugging Face; after that it works offline. For better
accuracy (slower), set `JARVIS_STT_MODEL=small.en` in `backend/.env`.

The browser asks for microphone permission the first time.

## Try tools directly (no LLM needed)

```bash
cd backend
uv run python -m app.tools calculate '{"expression": "(1200 * 0.15) + 40"}'
uv run python -m app.tools get_current_time '{"timezone": "Asia/Tokyo"}'
uv run python -m app.tools get_weather '{"location": "Boston"}'
```

## Chat via the API

```bash
curl -s localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message": "What is the weather in Boston and what time is it there?"}' | python3 -m json.tool
```
