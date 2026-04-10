"""Tests for the LLM-output-recovery helpers in core.agent.

These functions exist *because* LLMs return malformed JSON. The tests pin
the contract so future refactors don't reintroduce the bugs we already fixed.
"""
import json

import pytest

from core.agent import _normalize_tool_call, _parse_json_safely


class TestParseJsonSafely:
    def test_clean_json(self):
        out = _parse_json_safely('{"type": "final", "answer": "hi"}')
        assert out == {"type": "final", "answer": "hi"}

    def test_with_whitespace(self):
        out = _parse_json_safely('  {"a": 1}  \n')
        assert out == {"a": 1}

    def test_json_with_trailing_prose(self):
        text = '{"type": "final", "answer": "yes"} -- some explanation'
        out = _parse_json_safely(text)
        assert out["type"] == "final"

    def test_json_in_prose(self):
        text = 'Here is my response: {"type": "final", "answer": "hi"}'
        out = _parse_json_safely(text)
        assert out["type"] == "final"

    def test_no_json_at_all_raises(self):
        with pytest.raises(ValueError):
            _parse_json_safely("just plain text, no braces")

    def test_unwrap_raw_model_json(self):
        """Legacy history format: a single 'raw_model_json' string field."""
        inner = json.dumps({"type": "final", "answer": "yo"})
        wrapped = json.dumps({"raw_model_json": inner})
        out = _parse_json_safely(wrapped)
        assert out == {"type": "final", "answer": "yo"}

    def test_empty_string_raises(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _parse_json_safely("")


class TestNormalizeToolCall:
    def setup_method(self):
        # Tools dict — values don't matter, only keys are checked
        self.tools = {"weather": object(), "skill_creator": object(), "datetime": object()}

    def test_already_correct_tool_call(self):
        data = {"type": "tool_call", "tool": "weather", "args": {"city": "Paris"}}
        out = _normalize_tool_call(data, self.tools)
        assert out is data
        assert out["type"] == "tool_call"

    def test_already_final(self):
        data = {"type": "final", "answer": "hello"}
        out = _normalize_tool_call(data, self.tools)
        assert out is data

    def test_type_is_skill_name_recovery(self):
        """LLM returned {"type": "skill_creator", "action": "create", ...}
        instead of {"type": "tool_call", "tool": "skill_creator", "args": {...}}.
        Recovery rewrites it."""# ---------- _parse_json_safely ----------

        data = {
            "type": "skill_creator",
            "action": "create",
            "name": "mom_joke",
            "description": "tells a joke",
        }
        out = _normalize_tool_call(data, self.tools)
        assert out["type"] == "tool_call"
        assert out["tool"] == "skill_creator"
        assert out["args"] == {
            "action": "create",
            "name": "mom_joke",
            "description": "tells a joke",
        }
        assert "why" in out

    def test_type_is_skill_name_preserves_why(self):
        data = {
            "type": "weather",
            "city": "Berlin",
            "why": "user asked for weather",
        }
        out = _normalize_tool_call(data, self.tools)
        assert out["type"] == "tool_call"
        assert out["tool"] == "weather"
        assert out["args"] == {"city": "Berlin"}
        assert out["why"] == "user asked for weather"

    def test_top_level_tool_field_recovery(self):
        """LLM returned {"tool": "weather", "city": "Paris"} with no type."""
        data = {"tool": "weather", "city": "Paris"}
        out = _normalize_tool_call(data, self.tools)
        assert out["type"] == "tool_call"
        assert out["tool"] == "weather"
        assert out["args"] == {"city": "Paris"}

    def test_top_level_tool_with_existing_args(self):
        data = {"tool": "weather", "args": {"city": "Paris"}}
        out = _normalize_tool_call(data, self.tools)
        assert out["type"] == "tool_call"
        assert out["args"] == {"city": "Paris"}

    def test_type_unknown_no_match_passthrough(self):
        """Type is something we don't recognize and there's no `tool` field —
        leave the data alone for the caller to handle."""
        data = {"type": "weird_thing", "blah": 1}
        out = _normalize_tool_call(data, self.tools)
        assert out == {"type": "weird_thing", "blah": 1}

    def test_no_type_no_tool_passthrough(self):
        data = {"random": "data"}
        out = _normalize_tool_call(data, self.tools)
        assert out == {"random": "data"}

    def test_top_level_tool_unknown(self):
        data = {"tool": "nonexistent_tool", "x": 1}
        # Unknown tool — should not auto-recover
        out = _normalize_tool_call(data, self.tools)
        assert out.get("type") != "tool_call" or out.get("tool") != "nonexistent_tool" or "type" not in out
