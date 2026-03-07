from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from observability.timing import Timer

SYSTEM_PROMPT = """
You are a compact tool-using agent.

You have tools:
- vector_add(text, meta={...})
- vector_search(query, k=5)

You may also answer directly without tool calls.

You must ALWAYS output STRICT JSON, in one of the two forms:

A) Tool call:
{
  "type": "tool_call",
  "tool": "<tool_name>",
  "args": { ... },
  "why": "<short reason>"
}

B) Final answer:
{
  "type": "final",
  "answer": "<answer to the user>",
  "notes": "<optional constraints/assumptions>"
}

Rules:
- Never fabricate tool results.
- Prefer vector_search when you might have relevant prior memory.
- Use vector_add to store durable facts, decisions, preferences, or short summaries.
- In type="final", answer MUST be a string (not an object/array).
- Keep tool args minimal and valid.
""".strip()


def _parse_json_safely(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError(f"Model did not return JSON. Got: {text[:300]}")
    return json.loads(m.group(0))


def _format_memory_hits(hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return "Relevant memories: (none)"
    lines = ["Relevant memories (semantic search):"]
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        dist = h.get("distance")
        tag = meta.get("tag") or meta.get("type") or ""
        lines.append(f"{i}. [distance={dist:.4f}] {('(' + str(tag) + ') ') if tag else ''}{h.get('text','')}")
    return "\n".join(lines)


class AgentService:
    def __init__(self, history_store, vector_store, chat_client, tool_registry, context_tail: int = 30, memory_hits: int = 5):
        self.history_store = history_store
        self.vector_store = vector_store
        self.chat_client = chat_client
        self.tool_registry = tool_registry
        self.context_tail = context_tail
        self.memory_hits = memory_hits

    def run(self, query: str, session_id: Optional[int], remember: bool = True, max_steps: int = 6) -> dict[str, Any]:
        timer = Timer()
        sid = session_id or self.history_store.create_session()
        debug_lines: List[str] = []
        timings: Dict[str, float] = {}

        self.history_store.add_message(sid, "user", query)
        timer.mark("sqlite_add_user_s")

        memories, vtimings = self.vector_store.search_with_timings(query, k=self.memory_hits)
        timings["vector_search_total_s"] = vtimings.get("vector_search_total_s", 0.0)
        timings["vector_search_embed_s"] = vtimings.get("ollama_embed_s", 0.0)
        timings["vector_search_chroma_query_s"] = vtimings.get("chroma_query_s", 0.0)
        debug_lines.append(f"[vector] hits={len(memories)}")

        tail = self.history_store.load_tail(sid, limit=self.context_tail)
        timer.mark("sqlite_load_tail_s")

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": _format_memory_hits(memories)},
            *tail,
            {"role": "user", "content": query},
        ]

        def vector_add(text: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
            meta = dict(meta or {})
            meta.setdefault("session_id", sid)
            return self.vector_store.add_text(text, meta)

        def vector_search(q: str, k: int = 5) -> Dict[str, Any]:
            return {"hits": self.vector_store.search_text(q, k=k)}

        tools = {
            "vector_add": vector_add,
            "vector_search": vector_search,
        }

        for step in range(1, max_steps + 1):
            debug_lines.append(f"[agent] step={step}")
            raw, llm_s = self.chat_client.complete_json(messages)
            timings.setdefault("llm_chat_s_total", 0.0)
            timings["llm_chat_s_total"] += llm_s
            debug_lines.append(f"[llm] chat_s={llm_s:.4f}")

            self.history_store.add_message(sid, "assistant", {"raw_model_json": raw})

            data = _parse_json_safely(raw)

            if data.get("type") == "final":
                raw_answer = data.get("answer", "")
                answer = raw_answer if isinstance(raw_answer, str) else json.dumps(raw_answer, ensure_ascii=False, indent=2)
                self.history_store.add_message(sid, "assistant", answer)

                if remember and answer.strip():
                    # safe minimal auto-memory: only store short structured summaries if model explicitly asks via tool
                    pass

                timings.update(timer.as_dict())
                return {
                    "session_id": sid,
                    "answer": answer,
                    "meta": {
                        "timings": timings,
                        "step_count": step,
                        "model": self.chat_client.model,
                    },
                    "memories": memories,
                    "debug_log": "\n".join(debug_lines),
                }

            if data.get("type") != "tool_call":
                answer = f"(fallback) {raw}"
                self.history_store.add_message(sid, "assistant", answer)
                timings.update(timer.as_dict())
                return {
                    "session_id": sid,
                    "answer": answer,
                    "meta": {
                        "timings": timings,
                        "step_count": step,
                        "fallback": True,
                        "model": self.chat_client.model,
                    },
                    "memories": memories,
                    "debug_log": "\n".join(debug_lines),
                }

            tool = data.get("tool")
            args = data.get("args", {}) or {}
            debug_lines.append(f"[tool] call={tool} args={args}")

            if tool not in tools:
                tool_result = {"error": f"Unknown tool: {tool}", "available": list(tools.keys())}
            else:
                t0 = time.perf_counter()
                try:
                    tool_result = tools[tool](**args)
                except Exception as e:
                    tool_result = {"error": str(e), "tool": tool, "args": args}
                timings.setdefault("tool_s_total", 0.0)
                timings["tool_s_total"] += time.perf_counter() - t0
                debug_lines.append(f"[tool] result={str(tool_result)[:200]}")

            self.history_store.add_message(sid, "tool", tool_result)
            messages.append({"role": "assistant", "content": json.dumps(data, ensure_ascii=False)})
            messages.append({"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)})
            messages.append({"role": "user", "content": "Continue using the tool result."})

        answer = "I could not finish within max_steps. Please refine the goal or increase max_steps."
        self.history_store.add_message(sid, "assistant", answer)
        timings.update(timer.as_dict())
        return {
            "session_id": sid,
            "answer": answer,
            "meta": {
                "timings": timings,
                "step_count": max_steps,
                "max_steps_hit": True,
                "model": self.chat_client.model,
            },
            "memories": memories,
            "debug_log": "\n".join(debug_lines),
        }
