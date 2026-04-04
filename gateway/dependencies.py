from dataclasses import dataclass
import os

from core.agent import AgentService
from llm.ollama_client import OllamaChatClient
from llm.embeddings_client import OllamaEmbeddingsClient
from memory.history_store import HistoryStore
from memory.vector_store import VectorStore
from tools.registry import ToolRegistry
from tools.vector_add import VectorAddTool
from tools.vector_search import VectorSearchTool
from skills.registry import SkillRegistry
from skills.weather import WeatherSkill
from skills.datetime_skill import DateTimeSkill
from skills.http_request import HttpRequestSkill
from skills.shell_command import ShellCommandSkill


@dataclass
class Container:
    agent: AgentService
    history: HistoryStore
    vector: VectorStore
    tools: ToolRegistry
    skills: SkillRegistry
    chat: object  # OllamaChatClient or OpenAIChatClient
    embed: object  # OllamaEmbeddingsClient or OpenAIEmbeddingsClient


def _build_llm_clients(provider: str):
    """Build chat + embeddings clients based on LLM_PROVIDER env var."""
    if provider == "openai":
        from llm.openai_client import OpenAIChatClient, OpenAIEmbeddingsClient
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        embed_model = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        timeout = float(os.environ.get("OPENAI_TIMEOUT", "120"))
        chat = OpenAIChatClient(api_key=api_key, model=chat_model, base_url=base_url, timeout=timeout)
        embed = OpenAIEmbeddingsClient(api_key=api_key, model=embed_model, base_url=base_url, timeout=timeout)
        return chat, embed

    # Default: ollama
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3:latest")
    ollama_timeout = float(os.environ.get("OLLAMA_TIMEOUT", "120"))
    ollama_embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    chat = OllamaChatClient(ollama_url, ollama_model, timeout=ollama_timeout)
    embed = OllamaEmbeddingsClient(ollama_url, ollama_embed_model, timeout=ollama_timeout)
    return chat, embed


def build_container() -> Container:
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    sqlite_path = os.environ.get("AGENT_DB", os.path.join(data_dir, "agent_memory.sqlite3"))
    vector_dir = os.environ.get("AGENT_VECTOR_DIR", os.path.join(data_dir, "vector_db"))
    vector_collection = os.environ.get("AGENT_VECTOR_COLLECTION", "memories")
    context_tail = int(os.environ.get("AGENT_CONTEXT_TAIL", "30"))
    memory_hits = int(os.environ.get("AGENT_MEMORY_HITS", "5"))
    dedup_distance = float(os.environ.get("AGENT_DEDUP_DISTANCE", "0.08"))

    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    chat, embed = _build_llm_clients(provider)

    history = HistoryStore(sqlite_path)
    vector = VectorStore(
        persist_dir=vector_dir,
        collection_name=vector_collection,
        embeddings_client=embed,
        dedup_distance=dedup_distance,
    )

    tools = ToolRegistry()
    tools.register(VectorAddTool(vector_store=vector))
    tools.register(VectorSearchTool(vector_store=vector))

    # Skills
    skills = SkillRegistry()
    skills.register(WeatherSkill())
    skills.register(DateTimeSkill())
    skills.register(HttpRequestSkill(
        timeout=float(os.environ.get("SKILL_HTTP_TIMEOUT", "30")),
    ))
    shell_enabled = os.environ.get("SKILL_SHELL_ENABLED", "false").lower() in ("true", "1", "yes")
    skills.register(ShellCommandSkill(enabled=shell_enabled))

    agent = AgentService(
        history_store=history,
        vector_store=vector,
        chat_client=chat,
        tool_registry=tools,
        skill_registry=skills,
        context_tail=context_tail,
        memory_hits=memory_hits,
    )

    return Container(agent=agent, history=history, vector=vector,
                     tools=tools, skills=skills, chat=chat, embed=embed)
