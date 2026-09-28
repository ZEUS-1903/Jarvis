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
ollama serve                 # leave running (skip if the Ollama menu-bar app is open)
```

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
