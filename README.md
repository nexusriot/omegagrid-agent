# Ollama Agent Stack (SQLite + Vector Memory)

This stack provides:
- FastAPI backend: agent + SQLite history + ChromaDB vector memory (Ollama embeddings)
- React frontend (Vite build served by nginx)
- docker-compose with persistent host storage in `./data`

## Requirements
- Docker + docker-compose
- Local Ollama running on the host
- An embeddings model installed in Ollama (example):
  - `ollama pull nomic-embed-text`

## Run (docker-compose)
1. Edit `.env` if needed.
   - On Linux, `host.docker.internal` may not work. Use your host IP or run Ollama in a container.
2. Start:
   - `docker compose up --build`

Frontend:
- http://localhost:${FRONTEND_PORT}

Backend:
- http://localhost:${BACKEND_PORT}/health

## API
- POST `/api/query`  { query, session_id?, remember?, max_steps? }
- GET  `/api/sessions`
- POST `/api/sessions/new`
- POST `/api/memory/add`
- POST `/api/memory/search`

## CLI (REST)
From host (outside docker), with backend running:
- `python backend/cli.py --api http://localhost:8000 --new`
- `python backend/cli.py --api http://localhost:8000 --session 1 "hello"`

## Persistence
All persistent data goes to `./data`:
- `./data/agent_memory.sqlite3`
- `./data/vector_db/` (Chroma)

## Deduplication
When storing a memory item:
1) Exact dedup by SHA-256 hash stored in metadata
2) Semantic dedup by nearest neighbor distance <= `AGENT_DEDUP_DISTANCE` (cosine space)
