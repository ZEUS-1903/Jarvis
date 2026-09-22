# JARVIS

A personal AI assistant, built incrementally as a learning project.
Design: [docs/v1-architecture.md](docs/v1-architecture.md)

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
