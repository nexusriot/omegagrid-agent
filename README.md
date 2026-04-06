# OmegaGrid Agent

PoC AI agent platform __which we deserve__ with tool-calling loop, vector memory, conversation history, skills system, and multi-provider LLM support. 


### /b/-lobster way!


<p align="center" width="100%">
    <img width="70%" src="b-claw.png"> 
</p>


## Architecture

```
gateway/          FastAPI backend & API routes
core/             Agent orchestration loop
memory/           SQLite history + ChromaDB vector memory
llm/              LLM clients (Ollama + OpenAI)
tools/            Tool registry & tool adapters (vector_add, vector_search)
skills/           Skill system (weather, datetime, http_request, shell)
observability/    Timings / tracing helpers
integrations/     CLI + Telegram bot
frontend/         React UI (Query + History)
```

## Quick Start

```bash
cp .env.example .env
# Edit .env with your settings (Ollama URL, or OpenAI key)
docker compose up --build
```

- **Web UI**: http://localhost:8088
- **API**: http://localhost:8000
- **Health**: http://localhost:8000/health

---

## LLM Providers

### Ollama (default)

```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3:latest
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
```

### OpenAI Codex

```env
LLM_PROVIDER=openai-codex
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-5.3-codex
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_API_MODE=responses
OPENAI_REASONING_EFFORT=medium
```

Codex models use the OpenAI Responses API, so this project now switches to `/responses` automatically for `openai-codex` (or whenever the configured chat model contains `codex`).

You can also point `OPENAI_BASE_URL` at any OpenAI-compatible endpoint (Azure, local vLLM, LiteLLM, etc.).

---

## Skills

Skills are higher-level capabilities the agent can invoke. They appear as callable tools in the agent's system prompt.

### Built-in Skills

| Skill | Description | Config |
|-------|-------------|--------|
| `weather` | Current weather for any city (Open-Meteo, no API key) | - |
| `datetime` | Current UTC date/time | - |
| `http_request` | Call external HTTP APIs (GET/POST) | `SKILL_HTTP_TIMEOUT` |
| `shell` | Execute shell commands (disabled by default) | `SKILL_SHELL_ENABLED=true` |
| `web_scrape` | Fetch a web page and return clean text (HTML stripped) | `SKILL_HTTP_TIMEOUT` |
| `dns_lookup` | DNS record lookup (A, AAAA, MX, TXT, CNAME, NS, SOA, PTR, SRV) | - |
| `ping_check` | TCP reachability check with latency (host:port) | - |
| `cron_schedule` | Parse cron expressions, explain in English, show next run times | - |
| `schedule_task` | Create/list/delete recurring tasks (runs skills on cron, notifies Telegram) | `TELEGRAM_BOT_TOKEN` |

### Built-in Tools

| Tool | Description |
|------|-------------|
| `vector_add(text, meta)` | Store durable facts, decisions, or preferences in vector memory |
| `vector_search(query, k)` | Semantic similarity search over stored memories |

### Creating a Custom Skill

#### Option A: Python skill

1. Create a file in `skills/`, e.g. `skills/my_skill.py`:

```python
from skills.base import BaseSkill

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something useful"
    parameters = {
        "input": {"type": "string", "description": "The input", "required": True},
    }

    def execute(self, input: str, **kwargs):
        return {"result": f"Processed: {input}"}
```

2. Register it in `gateway/dependencies.py`:

```python
from skills.my_skill import MySkill
# ... inside build_container():
skills.register(MySkill())
```

The agent will automatically see and use the skill.

#### Option B: Markdown skill (no Python required)

Create a `.md` file in the `skills/` directory. Markdown skills are loaded automatically at startup.

1. Create `skills/my_skill.md`:

```markdown
---
name: my_skill
description: Does something useful
endpoint: https://api.example.com/action
method: GET
parameters:
  city:
    type: string
    description: The city to look up
    required: true
  format:
    type: string
    description: Output format (json or text)
    required: false
---

When using this skill, always include the country name alongside the city
for more accurate results. Prefer JSON format unless the user asks for plain text.
```

**Frontmatter fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Unique skill identifier (used as tool name in agent) |
| `description` | yes | Short description shown to the LLM |
| `parameters` | yes | Parameter schema (same format as Python skills) |
| `endpoint` | no | HTTP endpoint to call (enables auto-HTTP execution) |
| `method` | no | HTTP method: GET or POST (default GET) |

**Body (below frontmatter):** Optional free-text instructions appended to the LLM system prompt when this skill is available. Use this for prompt engineering, constraints, or examples.

Markdown skills without an `endpoint` act as **prompt-only skills** -- the agent sees them as capabilities and uses the body text as guidance, but execution relies on other tools (e.g. `http_request`).

### API Endpoints

- `GET /api/skills` - List all loaded skills
- `GET /api/tools` - List all tools
- `POST /api/query` - Query the agent (skills are auto-available)

---

## Telegram Bot Setup

### Step 1: Create a bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g. "OmegaGrid Agent") and username (e.g. `omegagrid_agent_bot`)
4. BotFather will give you a token like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Configure

Add to your `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
GATEWAY_URL=http://gateway:8000
BOT_AUTH_ENABLED=true
BOT_ADMIN_ID=123456789
BOT_AUTH_DB=/app/data/telegram_auth.sqlite3
```

When auth is enabled, only `BOT_ADMIN_ID` and users added by the admin can use the bot. The admin can authorize people with `/auth_add <telegram_id>`.

### Step 3: Run

**Option A - Docker (recommended)**

Uncomment the `telegram-bot` service in `docker-compose.yml`, then:

```bash
docker compose up --build
```

**Option B - Standalone**

```bash
export TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
export GATEWAY_URL=http://127.0.0.1:8000
python -m integrations.telegram.run
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Reset session, show help |
| `/ask <question>` | Explicitly ask the agent |
| `/new` | Start a fresh session |
| `/skills` | List available skills |
| `/auth_add <telegram_id>` | Admin only: authorize a Telegram user |
| `/auth_list` | Admin only: list authorized users |
| *(any text)* | Automatically sent to the agent |

Each Telegram user gets their own session (tracked by chat ID). Sessions persist across messages until `/start` or `/new`.

---

## External Tool Calling

The agent can call external services through two skills:

### HTTP Requests

The `http_request` skill lets the agent call any HTTP API:

```
Agent: I'll check the API for you.
→ tool_call: http_request(url="https://api.example.com/data", method="GET")
```

### Shell Commands

The `shell` skill is **disabled by default** for safety. Enable with:

```env
SKILL_SHELL_ENABLED=true
```

Dangerous commands (`rm -rf /`, `mkfs`, `shutdown`, etc.) are blocked. The agent can then run:

```
→ tool_call: shell(command="df -h", timeout=10)
```

---

## Scheduled Tasks

The agent can create recurring tasks that run skills on a cron schedule and optionally push results to Telegram.

### Usage via Telegram

Just tell the agent what you want in natural language:

```
"every 5 minutes ping check mydomain.com and send to telegram"
"schedule a weather check for London every hour"
"list my scheduled tasks"
"delete scheduled task 3"
```

The agent uses the `schedule_task` skill to create/list/delete tasks. When `notify_telegram_chat_id` is set, results are pushed to that Telegram chat automatically.

### Usage via API

```bash
# Create a scheduled task
curl -X POST http://localhost:8000/api/scheduler/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "ping mydomain.com",
    "cron_expr": "*/5 * * * *",
    "skill": "ping_check",
    "args": {"host": "mydomain.com"},
    "notify_telegram_chat_id": 11111111
  }'

# List tasks
curl http://localhost:8000/api/scheduler/tasks

# Enable/disable
curl -X POST http://localhost:8000/api/scheduler/tasks/1/disable
curl -X POST http://localhost:8000/api/scheduler/tasks/1/enable

# Delete
curl -X DELETE http://localhost:8000/api/scheduler/tasks/1
```

### How it works

1. Tasks are stored in SQLite (`./data/scheduler.sqlite3`)
2. A background thread in the gateway checks every 60 seconds
3. If a task's cron expression matches the current minute, the configured skill is executed
4. If `notify_telegram_chat_id` is set, the result is pushed to Telegram via the bot token
5. The gateway needs `TELEGRAM_BOT_TOKEN` in its environment for push notifications

---

## Data Persistence

- **SQLite** (`./data/agent_memory.sqlite3`) — sessions & conversation messages
- **SQLite** (`./data/scheduler.sqlite3`) — scheduled tasks
- **ChromaDB** (`./data/vector_db/`) — vector embeddings for semantic memory

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai`, or `openai-codex` |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3:latest` | Ollama chat model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Ollama embeddings model |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout (seconds) |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | OpenAI chat model |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | OpenAI embeddings model |
| `OPENAI_TIMEOUT` | `120` | OpenAI request timeout (seconds) |
| `OPENAI_API_MODE` | auto | `chat_completions` or `responses`; auto-selects `responses` for Codex models |
| `OPENAI_REASONING_EFFORT` | `medium` | Reasoning effort for Responses API capable models |
| `AGENT_VECTOR_COLLECTION` | `memories` | ChromaDB collection name |
| `AGENT_CONTEXT_TAIL` | `30` | Messages to include as context |
| `AGENT_MEMORY_HITS` | `5` | Max vector search results |
| `AGENT_DEDUP_DISTANCE` | `0.08` | Dedup threshold for vector memory |
| `SKILL_SHELL_ENABLED` | `false` | Enable shell command skill |
| `SKILL_HTTP_TIMEOUT` | `30` | HTTP request skill timeout |
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot token from BotFather |
| `GATEWAY_URL` | `http://127.0.0.1:8000` | Gateway URL for Telegram bot |
| `BOT_AUTH_ENABLED` | `false` | Enable sqlite-backed Telegram auth allowlist |
| `BOT_ADMIN_ID` | - | Admin Telegram ID allowed to manage users |
| `BOT_AUTH_DB` | `/app/data/telegram_auth.sqlite3` | sqlite DB for Telegram auth allowlist |
| `BACKEND_PORT` | `8000` | Gateway exposed port |
| `FRONTEND_PORT` | `8088` | Frontend exposed port |
