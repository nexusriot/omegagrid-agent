# Agent Platform
This archive integrates the current working agent code into a more production-oriented layout:

- `gateway/` — FastAPI entrypoint and API routes
- `core/` — orchestration logic
- `memory/` — SQLite history + Chroma vector memory
- `llm/` — Ollama chat / embeddings clients
- `tools/` — tool registry and tool adapters
- `observability/` — timings / tracing helpers
- `integrations/` — CLI + Telegram skeleton
- `frontend/` — React UI (Query + History)

## Run

```bash
cp .env.example .env
docker compose up --build
```

## Notes

- Backend build context is the project root so `gateway/` can import `core/`, `memory/`, `llm/`, etc.
- Vector memory uses ChromaDB with local persistence in `./data/vector_db`.
- SQLite history persists in `./data/agent_memory.sqlite3`.
- Ollama chat uses `/api/chat`.
- Embeddings client tries:
  1. `/api/embed`
  2. `/v1/embeddings`
  3. `/api/embeddings`

## Next recommended steps

1. Replace Telegram skeleton with real handlers wired to gateway.
2. Add streaming endpoint (`/api/query/stream`).
3. Add Memory page for manual add/search/edit in frontend.
4. Add request IDs and structured logs.
