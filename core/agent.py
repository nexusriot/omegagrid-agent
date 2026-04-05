from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from observability.timing import Timer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """
You are a compact tool-using agent.

You have tools:
- vector_add(text, meta={{...}})  -- store a durable fact / decision / preference
- vector_search(query, k=5)      -- semantic search over stored memories
{skills_block}

You must ALWAYS output STRICT JSON, in one of the two forms:

A) Tool call:
{{
  "type": "tool_call",
  "tool": "<tool_name>",
  "args": {{ ... }},
  "why": "<short reason>"
}}

B) Final answer (ONLY after you have all the information you need):
{{
  "type": "final",
  "answer": "<plain-text answer to the user>",
  "notes": "<optional constraints/assumptions>"
}}

CRITICAL RULES:
- You MUST use the appropriate tool to get real data. NEVER invent, guess, or
  fabricate tool results. If you need weather, time, DNS, HTTP data etc. you
  MUST call the corresponding tool/skill first, then give a final answer based
  on the real tool result.
- NEVER respond with a final answer that contains data you did not obtain from
  a tool call or from the conversation context. If you don't have the data, call
  the tool first.
- Prefer vector_search BEFORE answering questions where prior memory may help.
- Use vector_add to store durable facts, decisions, preferences, or summaries
  the user shares with you.
- In type="final", answer MUST be a human-readable plain-text string
  (not raw JSON, not an object/array). Explain the result to the user naturally.
- Keep tool args minimal and valid.
""".strip()


def _build_system_prompt(skill_registry=None) -> str:
    skills_block = ""
    if skill_registry:
        desc = skill_registry.describe_for_prompt()
        if desc:
            skills_block = f"\nYou also have skills (call them like tools):\n{desc}\n"
    return _SYSTEM_PROMPT_TEMPLATE.format(skills_block=skills_block)


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
    def __init__(self, history_store, vector_store, chat_client, tool_registry,
                 skill_registry=None, context_tail: int = 30, memory_hits: int = 5):
        self.history_store = history_store
        self.vector_store = vector_store
        self.chat_client = chat_client
        self.tool_registry = tool_registry
        self.skill_registry = skill_registry
        self.context_tail = context_tail
        self.memory_hits = memory_hits

    def run(self, query: str, session_id: Optional[int] = None, remember: bool = True, max_steps: int = 6) -> dict[str, Any]:
        timer = Timer()
        sid = session_id or self.history_store.create_session()
        debug_lines: List[str] = []
        timings: Dict[str, float] = {}

        self.history_store.add_message(sid, "user", query)
        timer.mark("sqlite_add_user_s")

        try:
            memories, vtimings = self.vector_store.search_with_timings(query, k=self.memory_hits)
        except Exception as e:
            logger.error("Vector search failed: %s", e)
            memories, vtimings = [], {}
            debug_lines.append(f"[memory] ERROR: vector search failed: {e}")
        timings["vector_search_total_s"] = vtimings.get("vector_search_total_s", 0.0)
        timings["vector_search_embed_s"] = vtimings.get("ollama_embed_s", 0.0)
        timings["vector_search_chroma_query_s"] = vtimings.get("chroma_query_s", 0.0)
        debug_lines.append(f"[memory] initial vector search for query: {query[:120]}")
        debug_lines.append(f"[memory] hits={len(memories)}, embed_s={vtimings.get('ollama_embed_s', 0):.4f}, chroma_s={vtimings.get('chroma_query_s', 0):.4f}")
        for i, hit in enumerate(memories):
            debug_lines.append(f"[memory]   #{i+1} dist={hit.get('distance', '?'):.4f} text={str(hit.get('text', ''))[:120]}")

        tail = self.history_store.load_tail(sid, limit=self.context_tail)
        timer.mark("sqlite_load_tail_s")

        system_prompt = _build_system_prompt(self.skill_registry)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": _format_memory_hits(memories)},
            *tail,
            {"role": "user", "content": query},
        ]

        def vector_add(text: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
            meta = dict(meta or {})
            meta.setdefault("session_id", sid)
            return self.vector_store.add_text(text, meta)

        def vector_search(query: str = "", q: str = "", k: int = 5) -> Dict[str, Any]:
            """Accept both 'query' and 'q' param names since the LLM may use either."""
            search_query = query or q
            if not search_query:
                return {"hits": [], "error": "No query provided"}
            return {"hits": self.vector_store.search_text(search_query, k=k)}

        tools = {
            "vector_add": vector_add,
            "vector_search": vector_search,
        }

        # Register skills as callable tools
        skill_names = []
        if self.skill_registry:
            for skill_name in self.skill_registry.list_names():
                skill = self.skill_registry.get(skill_name)
                tools[skill_name] = lambda _s=skill, **kw: _s.execute(**kw)
                skill_names.append(skill_name)
        debug_lines.append(f"[init] tools={list(tools.keys())}")
        debug_lines.append(f"[init] skills={skill_names}")

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

            if data.get("type") not in ("tool_call", "final"):
                debug_lines.append(f"[fallback] LLM returned unexpected type={data.get('type')!r}, raw={raw[:300]}")
                # Try to extract a usable text answer from the malformed response
                answer = data.get("answer") or data.get("text") or data.get("result") or ""
                if not answer or not isinstance(answer, str):
                    # Re-prompt the LLM to give a proper final answer
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": (
                        "Your response was not valid JSON with type='final' or type='tool_call'. "
                        "Please respond with a proper JSON object. If you have enough information, "
                        "use {\"type\":\"final\",\"answer\":\"your plain-text answer\"}. "
                        "If you need data, use a tool_call."
                    )})
                    debug_lines.append("[fallback] re-prompting LLM for valid response")
                    continue
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
            is_skill = tool in skill_names
            kind = "skill" if is_skill else "tool"
            debug_lines.append(f"[{kind}] >>> CALL {tool}({json.dumps(args, ensure_ascii=False)[:200]}) reason={data.get('why', '-')}")

            if tool not in tools:
                tool_result = {"error": f"Unknown tool/skill: {tool}", "available": list(tools.keys())}
                debug_lines.append(f"[{kind}] ERROR unknown name '{tool}', available: {list(tools.keys())}")
            else:
                t0 = time.perf_counter()
                try:
                    tool_result = tools[tool](**args)
                except Exception as e:
                    tool_result = {"error": str(e), "tool": tool, "args": args}
                    debug_lines.append(f"[{kind}] EXCEPTION: {e}")
                elapsed = time.perf_counter() - t0
                timing_key = "skill_s_total" if is_skill else "tool_s_total"
                timings.setdefault(timing_key, 0.0)
                timings[timing_key] += elapsed
                debug_lines.append(f"[{kind}] <<< RESULT ({elapsed:.3f}s): {str(tool_result)[:300]}")

                # Extended logging for vector memory operations
                if tool == "vector_add":
                    skipped = tool_result.get("skipped", False)
                    reason = tool_result.get("reason", "")
                    mid = tool_result.get("memory_id", "?")
                    debug_lines.append(f"[memory] vector_add: id={mid}, skipped={skipped}, reason={reason}, text={str(args.get('text', ''))[:120]}")
                elif tool == "vector_search":
                    hits = tool_result.get("hits", [])
                    debug_lines.append(f"[memory] vector_search: query={str(args.get('q', args.get('query', '')))[:100]}, hits={len(hits)}")
                    for i, h in enumerate(hits):
                        debug_lines.append(f"[memory]   #{i+1} dist={h.get('distance', '?'):.4f} text={str(h.get('text', ''))[:120]}")

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
