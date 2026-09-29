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

### 2b. Database (PostgreSQL) — once

JARVIS stores conversations and long-term memory in PostgreSQL.

```bash
brew install postgresql@17
brew services start postgresql@17            # runs in the background, starts at login
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"   # add this line to ~/.zshrc too
createdb jarvis                              # the app's database
createdb jarvis_test                         # optional: used by the test suite
```

The default `JARVIS_DATABASE_URL=postgresql://localhost:5432/jarvis` works with
Homebrew's defaults (your macOS user, no password). Tables are created automatically
when the backend starts.

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

## Memory

JARVIS keeps a long-term memory of facts about you (open **Memory** in the header).

- Say "Remember that…" and it's saved right away.
- If JARVIS decides on its own that something is worth remembering, it becomes a
  *proposal* you approve or dismiss in the Memory panel (badge on the button).
- Passwords, card numbers and similar secrets are never stored.
- You can add and delete memories yourself in the panel.

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

## Hands-free: "Hey Jarvis"

Uses [openWakeWord](https://github.com/dscripka/openWakeWord) locally. Download the model once:

```bash
cd backend
uv run python -m app.voice wake-setup
```

In the UI, click **Hey Jarvis: off** to turn listening on (the mic stays on while enabled;
macOS shows the orange dot). Say *"Hey Jarvis"*, wait for the chime, then say your command.
JARVIS stops recording after about a second of silence.

- Triggers by itself? Raise `JARVIS_WAKE_THRESHOLD` (e.g. `0.7`) in `backend/.env`.
- Misses you? Lower it (e.g. `0.35`).
- Only the JARVIS page (`http://localhost:5173`) may connect to the wake word stream; if you
  run the frontend on another port, add it to `JARVIS_ALLOWED_ORIGINS`.

## Gmail & Google Calendar (read-only)

JARVIS can search and read your Gmail and read your Google Calendar. It cannot send,
delete or change anything yet.

**One-time Google Cloud setup (free, ~15 min):**

1. https://console.cloud.google.com → create a project `Jarvis`.
2. APIs & Services → Library → enable **Gmail API** and **Google Calendar API**.
3. Google Auth Platform (OAuth consent screen) → Get started → app name `Jarvis`,
   your email, Audience **External**.
4. Audience → Test users → add your own Gmail address.
5. Clients (Credentials) → Create client → **Desktop app** → Download JSON.
6. Save it as `backend/secrets/google_client.json` (git-ignored; never commit it).

**Connect** (opens your browser; approve the "unverified app" warning, it's your own app):

```bash
cd backend
uv run python -m app.google connect
uv run python -m app.google status
```

The token is stored in the macOS Keychain. While the Google app is in *Testing* mode, Google
expires it after 7 days: run `connect` again when JARVIS says access expired.
Revoke any time at https://myaccount.google.com/connections (and `python -m app.google disconnect`).

Email and calendar text is treated as untrusted: JARVIS summarizes it but never follows
instructions inside it.

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
