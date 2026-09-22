# JARVIS

A personal AI assistant, built incrementally as a learning project.
Design: [docs/v1-architecture.md](docs/v1-architecture.md)

## Prerequisite: a local LLM (free)

```bash
brew install ollama          # or the app from ollama.com
ollama pull qwen3:8b         # ~5 GB; fits a 16 GB Mac
ollama serve                 # skip if the Ollama app is already running
```

## Run the backend

```bash
cd backend
cp ../.env.example .env        # adjust timezone/units
uv sync
uv run uvicorn app.main:app --reload --port 8000
curl -i localhost:8000/api/health   # {"status":"ok"} + X-Request-ID header
uv run pytest                       # tests
```

Interactive API docs: http://localhost:8000/docs

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
