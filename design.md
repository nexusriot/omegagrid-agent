# OmegaGrid Agent -- Design Document

## Overview

OmegaGrid Agent is a tool-calling AI agent platform with vector memory, conversation history, a skills system, and multi-provider LLM support. It runs as a FastAPI backend with React frontend, CLI, and Telegram bot integrations.

## Architecture Diagram

```
                        +------------------+
                        |   Integrations   |
                        | CLI | Telegram   |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |  FastAPI Gateway  |  :8000
                        |  (gateway/)       |
                        +--------+---------+
                                 |
               +-----------------+------------------+
               |                 |                  |
       +-------v------+  +------v-------+  +-------v--------+
       |  AgentService |  | History API  |  | Memory/Skills  |
       |  (core/)      |  | Tools API    |  | Health API     |
       +-------+------+  +--------------+  +----------------+
               |
    +----------+----------+
    |          |          |
+---v---+ +---v----+ +---v---------+
|  LLM  | | Memory | | Tools/Skills|
| Client| | Layer  | | Registry    |
+---+---+ +---+----+ +------+------+
    |         |              |
    v         v              v
 Ollama   SQLite +       BaseSkill x8
 OpenAI   ChromaDB       BaseTool x2
                          *.md skills
```

## Core Loop (`core/agent.py` -- `AgentService.run()`)

The agent implements a strict **tool-calling loop** with up to `max_steps` (default 6) iterations:

```
User query
  |
  v
1. Store user message in SQLite history
2. Search vector DB for semantically relevant memories
3. Load conversation tail (last N messages)
4. Build system prompt (tools + skills descriptions)
  |
  v
+---> 5. Call LLM with messages (strict JSON output)
|     6. Parse JSON response
|       |
|       +-- type="final"     --> Return answer to user
|       +-- type="tool_call" --> Execute tool, append result, goto 5
|       +-- other/invalid    --> Re-prompt LLM with error, goto 5
```

## Components

### LLM Clients (`llm/`)

| Client | Provider | Endpoint | Notes |
|--------|----------|----------|-------|
| `OllamaChatClient` | Ollama | `/api/chat` | Local models, JSON mode |
| `OpenAIChatClient` | OpenAI / compatible | `/chat/completions` or `/responses` | Auto-selects Responses API for Codex models |
| `OllamaEmbeddingsClient` | Ollama | `/api/embed` (3 fallback endpoints) | Used for vector memory |
| `OpenAIEmbeddingsClient` | OpenAI | `/v1/embeddings` | `text-embedding-3-small` default |

All clients expose a common interface: `complete_json(messages) -> (text, elapsed)` and `embed(text) -> (vector, elapsed)`.

### Memory Layer (`memory/`)

**HistoryStore** (SQLite):
- Tables: `sessions`, `messages`
- Stores all conversation turns as JSON blobs
- `load_tail(session_id, limit)` provides rolling context window

**VectorStore** (ChromaDB):
- Single collection with cosine distance
- Two-tier deduplication: exact SHA256 hash, then semantic distance threshold (default 0.08)
- `add_text(text, meta)` -- store with dedup check
- `search_with_timings(query, k)` -- semantic nearest-neighbor search

### Tools (`tools/`)

Built-in tools available in every agent loop iteration:

| Tool | Description |
|------|-------------|
| `vector_add(text, meta)` | Store durable facts/decisions in vector memory |
| `vector_search(query, k)` | Semantic similarity search over stored memories |

### Skills (`skills/`)

Skills are higher-level capabilities registered at startup. They appear as callable tools in the agent's system prompt.

| Skill | Description | Key params |
|-------|-------------|------------|
| `weather` | Current weather via Open-Meteo (free, no key) | `city` |
| `datetime` | Current UTC date/time | (none) |
| `http_request` | HTTP GET/POST to external APIs | `url`, `method`, `body`, `headers` |
| `shell` | Execute shell commands (disabled by default) | `command`, `timeout` |
| `web_scrape` | Fetch URL, strip HTML, return text | `url`, `max_chars` |
| `dns_lookup` | DNS record resolution (dig + socket fallback) | `domain`, `record_type` |
| `ping_check` | TCP reachability check with latency | `host`, `port`, `timeout` |
| `cron_schedule` | Parse cron expressions, show next runs | `expression`, `count` |

Skills can also be defined as **Markdown files** (see `skills/*.md`). The agent loads `.md` skill definitions at startup, supporting declarative skill authoring without Python code.

### Markdown Skill Format

```markdown
---
name: my_skill
description: What this skill does
endpoint: https://api.example.com/data
method: GET
parameters:
  city:
    type: string
    description: City name
    required: true
---

Optional instructions or prompt context for the agent when using this skill.
```

### Dependency Injection (`gateway/dependencies.py`)

`build_container()` wires everything together at startup:
1. Selects LLM provider based on `LLM_PROVIDER` env var
2. Creates history store, vector store, tool registry, skill registry
3. Registers all built-in tools and skills
4. Loads markdown skill files from `skills/*.md`
5. Constructs `AgentService` with all dependencies

### API Endpoints (`gateway/api/`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/query` | Send query to agent (main entry point) |
| `POST` | `/api/sessions/new` | Create new conversation session |
| `GET` | `/api/sessions` | List sessions |
| `GET` | `/api/sessions/{id}/messages` | Get session messages |
| `POST` | `/api/memory/add` | Manually add to vector memory |
| `POST` | `/api/memory/search` | Manually search vector memory |
| `GET` | `/api/skills` | List loaded skills |
| `GET` | `/api/tools` | List loaded tools |
| `GET` | `/health` | Health check |

### Observability

- `Timer` class tracks cumulative timings per phase (LLM, embedding, ChromaDB, tools)
- `debug_log` returned in every response with step-by-step trace
- Tool calls logged with: tool name, args, reason, result (truncated), elapsed time
- Vector memory operations logged with: hit count, distances, add/skip decisions

### Integrations

- **CLI** (`integrations/cli/`): Simple HTTP client against gateway
- **Telegram** (`integrations/telegram/`): Per-user sessions, auth allowlist, bot commands
- **Frontend** (`frontend/`): React 18 + Vite UI

## Data Flow Example

```
User: "What's the weather in Berlin?"

1. AgentService.run("What's the weather in Berlin?")
2. vector_search("What's the weather in Berlin?", k=5) -> 0 relevant hits
3. LLM call #1 -> {"type":"tool_call", "tool":"weather", "args":{"city":"Berlin"}}
4. WeatherSkill.execute(city="Berlin") -> {temperature_c: 18, ...}
5. LLM call #2 -> {"type":"final", "answer":"It's 18C in Berlin with..."}
6. Return answer + debug_log + timings
```

## Key Design Decisions

1. **Strict JSON output**: LLM must always return JSON (tool_call or final). This enables reliable parsing and prevents free-form hallucination of tool results.
2. **Vector dedup**: Two-tier (hash + cosine distance) prevents memory bloat while keeping novel information.
3. **Skills vs Tools**: Tools are low-level (vector ops). Skills are user-facing capabilities (weather, HTTP, shell). Both use the same dispatch mechanism at runtime.
4. **Provider abstraction**: Common interface allows swapping Ollama / OpenAI / any compatible endpoint without changing agent code.
5. **Markdown skills**: Declarative skill definitions in `.md` files allow non-developers to add capabilities without writing Python.
