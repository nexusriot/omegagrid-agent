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


@dataclass
class Container:
    agent: AgentService
    history: HistoryStore
    vector: VectorStore
    tools: ToolRegistry
    chat: OllamaChatClient
    embed: OllamaEmbeddingsClient


def build_container() -> Container:
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    sqlite_path = os.environ.get("AGENT_DB", os.path.join(data_dir, "agent_memory.sqlite3"))
    vector_dir = os.environ.get("AGENT_VECTOR_DIR", os.path.join(data_dir, "vector_db"))
    vector_collection = os.environ.get("AGENT_VECTOR_COLLECTION", "memories")
    context_tail = int(os.environ.get("AGENT_CONTEXT_TAIL", "30"))
    memory_hits = int(os.environ.get("AGENT_MEMORY_HITS", "5"))
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3:latest")
    ollama_timeout = float(os.environ.get("OLLAMA_TIMEOUT", "120"))
    ollama_embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    dedup_distance = float(os.environ.get("AGENT_DEDUP_DISTANCE", "0.08"))

    history = HistoryStore(sqlite_path)
    embed = OllamaEmbeddingsClient(ollama_url, ollama_embed_model, timeout=ollama_timeout)
    vector = VectorStore(
        persist_dir=vector_dir,
        collection_name=vector_collection,
        embeddings_client=embed,
        dedup_distance=dedup_distance,
    )
    chat = OllamaChatClient(ollama_url, ollama_model, timeout=ollama_timeout)

    tools = ToolRegistry()
    tools.register(VectorAddTool(vector_store=vector))
    tools.register(VectorSearchTool(vector_store=vector))

    agent = AgentService(
        history_store=history,
        vector_store=vector,
        chat_client=chat,
        tool_registry=tools,
        context_tail=context_tail,
        memory_hits=memory_hits,
    )

    return Container(agent=agent, history=history, vector=vector, tools=tools, chat=chat, embed=embed)
