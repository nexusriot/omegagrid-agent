from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Tuple

import requests

from .sqlite_memory import MemoryDB
from .vector_memory import VectorMemory


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


def _ollama_chat(ollama_url: str, model: str, messages: List[Dict[str, Any]], timeout: float) -> Tuple[str, float]:
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    r = requests.post(f"{ollama_url.rstrip('/')}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["message"]["content"]
    return content, (time.perf_counter() - t0)


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


def run_agent_query(
    query: str,
    session_id: int,
    mem: MemoryDB,
    vmem: VectorMemory,
    context_tail: int,
    memory_hits: int,
    ollama_url: str,
    ollama_model: str,
    ollama_timeout: float,
    max_steps: int = 6,
    allow_remember: bool = True,
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], str]:
    """
    Returns: (answer, meta, memories, debug_log)
    """
    debug_lines: List[str] = []
    timings: Dict[str, float] = {}

    # Persist user message
    mem.add_message(session_id, "user", query)

    # Retrieve memories automatically and inject into prompt
    t0 = time.perf_counter()
    hits, t_v = vmem.search_with_timings(query, k=memory_hits)
    timings["vector_search_total_s"] = t_v.get("vector_search_total_s", 0.0)
    timings["vector_search_embed_s"] = t_v.get("ollama_embed_s", 0.0)
    timings["vector_search_chroma_query_s"] = t_v.get("chroma_query_s", 0.0)
    memories = hits
    debug_lines.append(f"[vector] hits={len(hits)}")

    # Load conversation tail from sqlite
    t1 = time.perf_counter()
    tail = mem.load_tail(session_id, context_tail)
    timings["sqlite_load_tail_s"] = time.perf_counter() - t1

    # Base messages
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": _format_memory_hits(hits)},
        *tail,
        {"role": "user", "content": query},
    ]

    # Tool bindings
    def vector_add(text: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        meta = dict(meta or {})
        meta.setdefault("session_id", session_id)
        return vmem.add(text=text, meta=meta)

    def vector_search(q: str, k: int = 5) -> Dict[str, Any]:
        return {"hits": vmem.search(query=q, k=k)}

    tools = {"vector_add": vector_add, "vector_search": vector_search}

    # Agent loop
    for step in range(1, max_steps + 1):
        debug_lines.append(f"[agent] step={step}")

        raw, t_llm = _ollama_chat(ollama_url, ollama_model, messages, ollama_timeout)
        timings.setdefault("llm_chat_s_total", 0.0)
        timings["llm_chat_s_total"] += t_llm
        debug_lines.append(f"[llm] chat_s={t_llm:.4f}")

        mem.add_message(session_id, "assistant", {"raw_model_json": raw})

        data = _parse_json_safely(raw)

        if data.get("type") == "final":
            raw_answer = data.get("answer", "")

            # Normalize answer to string for API stability
            if isinstance(raw_answer, str):
                answer = raw_answer
            else:
                answer = json.dumps(raw_answer, ensure_ascii=False, indent=2)

            mem.add_message(session_id, "assistant", answer)
            meta = {"timings": timings, "step_count": step}
            return answer, meta, memories, "\n".join(debug_lines)

        if data.get("type") != "tool_call":
            answer = f"(fallback) {raw}"
            mem.add_message(session_id, "assistant", answer)
            meta = {"timings": timings, "step_count": step, "fallback": True}
            return answer, meta, memories, "\n".join(debug_lines)

        tool = data.get("tool")
        args = data.get("args", {}) or {}
        debug_lines.append(f"[tool] call={tool} args={args}")

        if tool not in tools:
            tool_result = {"error": f"Unknown tool: {tool}", "available": list(tools.keys())}
        else:
            t_tool0 = time.perf_counter()
            try:
                tool_result = tools[tool](**args)
            except Exception as e:
                tool_result = {"error": str(e), "tool": tool, "args": args}
            t_tool = time.perf_counter() - t_tool0
            timings.setdefault("tool_s_total", 0.0)
            timings["tool_s_total"] += t_tool
            debug_lines.append(f"[tool] time_s={t_tool:.4f}")

        mem.add_message(session_id, "tool", tool_result)

        # Feed tool result back
        messages.append({"role": "assistant", "content": json.dumps(data, ensure_ascii=False)})
        messages.append({"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)})
        messages.append({"role": "user", "content": "Continue using the tool result."})

    answer = "I could not finish within max_steps. Please refine the goal or increase max_steps."
    mem.add_message(session_id, "assistant", answer)
    meta = {"timings": timings, "step_count": max_steps, "max_steps_hit": True}
    return answer, meta, memories, "\n".join(debug_lines)
