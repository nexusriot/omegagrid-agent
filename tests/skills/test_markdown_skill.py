"""Tests for the markdown skill engine: frontmatter parsing, placeholder
resolution, and pipeline execution with skill steps.

Pipeline tests use a stub `_skill_executor` so we never hit the network. The
HTTP step path is exercised separately via monkeypatched `requests.get/post`.
"""
import pytest

from skills.markdown_skill import (
    MarkdownSkill,
    _parse_frontmatter,
    _resolve_obj,
    _resolve_str,
    _resolve_value,
)


class TestParseFrontmatter:
    def test_valid(self):
        text = "---\nname: foo\ndescription: bar\n---\nbody text"
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "foo", "description": "bar"}
        assert body == "body text"

    def test_no_frontmatter(self):
        meta, body = _parse_frontmatter("just some text")
        assert meta == {}
        assert body == "just some text"

    def test_empty_string(self):
        meta, body = _parse_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_unclosed_frontmatter(self):
        meta, body = _parse_frontmatter("---\nname: foo\nno closing")
        assert meta == {}

    def test_unicode(self):
        text = "---\nname: foo\ndescription: héllo 🚀\n---\nbödy"
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "héllo 🚀"
        assert body == "bödy"

    def test_nested_yaml(self):
        text = (
            "---\n"
            "name: foo\n"
            "parameters:\n"
            "  x:\n"
            "    type: string\n"
            "    required: true\n"
            "---\n"
            "body"
        )
        meta, _body = _parse_frontmatter(text)
        assert meta["parameters"]["x"]["required"] is True



class TestResolveValue:
    def test_direct_param(self):
        assert _resolve_value("city", {"city": "Paris"}, {}) == "Paris"

    def test_step_dot_path(self):
        ctx = {"step1": {"data": {"value": 42}}}
        assert _resolve_value("step1.data.value", {}, ctx) == "42"

    def test_step_list_index(self):
        ctx = {"step1": {"items": ["a", "b", "c"]}}
        assert _resolve_value("step1.items.1", {}, ctx) == "b"

    def test_missing_key_leaves_placeholder(self):
        out = _resolve_value("nope", {}, {})
        assert out == "{{nope}}"

    def test_missing_step_path_returns_empty_str(self):
        ctx = {"step1": {"a": 1}}
        assert _resolve_value("step1.missing", {}, ctx) == ""

    def test_param_takes_precedence_over_ctx(self):
        ctx = {"city": {"name": "Berlin"}}
        # Plain param should win
        assert _resolve_value("city", {"city": "Paris"}, ctx) == "Paris"


class TestResolveStr:
    def test_single(self):
        assert _resolve_str("hello {{name}}", {"name": "world"}, {}) == "hello world"

    def test_multiple(self):
        out = _resolve_str("{{a}}-{{b}}", {"a": "1", "b": "2"}, {})
        assert out == "1-2"

    def test_no_placeholders(self):
        assert _resolve_str("plain text", {}, {}) == "plain text"

    def test_step_path(self):
        ctx = {"now": {"date": "2026-04-10"}}
        assert _resolve_str("date={{now.date}}", {}, ctx) == "date=2026-04-10"


class TestResolveObj:
    def test_dict(self):
        out = _resolve_obj({"k": "{{v}}"}, {"v": "x"}, {})
        assert out == {"k": "x"}

    def test_nested(self):
        obj = {"outer": {"inner": ["{{a}}", "{{b}}"]}}
        out = _resolve_obj(obj, {"a": "1", "b": "2"}, {})
        assert out == {"outer": {"inner": ["1", "2"]}}

    def test_non_string_passthrough(self):
        assert _resolve_obj(42, {}, {}) == 42
        assert _resolve_obj(None, {}, {}) is None
        assert _resolve_obj(True, {}, {}) is True



class TestPromptOnlyMode:
    def test_no_endpoint_no_steps(self):
        skill = MarkdownSkill(meta={"name": "noop", "description": "n"}, body="just instructions")
        out = skill.execute(foo="bar")
        assert "instructions" in out
        assert out["instructions"] == "just instructions"
        assert out["parameters_received"] == {"foo": "bar"}


class TestPipelineSkillSteps:
    def test_skill_step_passes_args_and_collects_result(self):
        calls = []

        def fake_executor(skill_name, args):
            calls.append((skill_name, args))
            if skill_name == "datetime":
                return {"date": "2026-04-10", "time": "12:00"}
            if skill_name == "echo":
                return {"echoed": args}
            return {"error": "unknown"}

        meta = {
            "name": "test_pipeline",
            "description": "test",
            "steps": [
                {"name": "now", "skill": "datetime"},
                {"name": "shout", "skill": "echo", "args": {"msg": "{{now.date}}"}},
            ],
        }
        skill = MarkdownSkill(meta=meta, body="", skill_executor=fake_executor)
        out = skill.execute()

        assert out["steps_completed"] == 2
        assert calls[0] == ("datetime", {})
        # Placeholder must have been resolved before calling the second skill
        assert calls[1] == ("echo", {"msg": "2026-04-10"})
        assert out["results"][1]["body"]["echoed"] == {"msg": "2026-04-10"}

    def test_skill_step_without_executor(self):
        meta = {
            "name": "p",
            "description": "p",
            "steps": [{"name": "x", "skill": "datetime"}],
        }
        skill = MarkdownSkill(meta=meta, body="", skill_executor=None)
        out = skill.execute()
        assert out["results"][0]["body"]["error"]
        assert "skill executor" in out["results"][0]["body"]["error"]

    def test_skill_step_executor_raises(self):
        def boom(name, args):
            raise RuntimeError("boom")

        meta = {
            "name": "p",
            "description": "p",
            "steps": [{"name": "x", "skill": "datetime"}],
        }
        skill = MarkdownSkill(meta=meta, body="", skill_executor=boom)
        out = skill.execute()
        assert "error" in out["results"][0]["body"]
        assert out["results"][0]["body"]["error"] == "boom"

    def test_step_with_neither_endpoint_nor_skill(self):
        meta = {
            "name": "p",
            "description": "p",
            "steps": [{"name": "broken"}],
        }
        skill = MarkdownSkill(meta=meta, body="", skill_executor=lambda *a, **k: {})
        out = skill.execute()
        assert "error" in out["results"][0]


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = "raw"

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class TestPipelineHttpSteps:
    def test_http_get_resolves_placeholders_in_url(self, monkeypatch):
        captured = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return _FakeResponse({"ok": True})

        monkeypatch.setattr("skills.markdown_skill.requests.get", fake_get)

        meta = {
            "name": "p",
            "description": "p",
            "steps": [
                {
                    "name": "get",
                    "endpoint": "https://api.example.com/{{kind}}/items",
                    "method": "GET",
                },
            ],
        }
        skill = MarkdownSkill(meta=meta, body="")
        out = skill.execute(kind="users")

        assert captured["url"] == "https://api.example.com/users/items"
        assert out["steps_completed"] == 1
        assert out["results"][0]["status"] == 200
        assert out["results"][0]["body"] == {"ok": True}

    def test_http_post_resolves_body_placeholders(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, headers=None, params=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse({"created": True}, status_code=201)

        monkeypatch.setattr("skills.markdown_skill.requests.post", fake_post)

        meta = {
            "name": "p",
            "description": "p",
            "steps": [
                {
                    "name": "create",
                    "endpoint": "https://api.example.com/users",
                    "method": "POST",
                    "body": {"name": "{{username}}"},
                },
            ],
        }
        skill = MarkdownSkill(meta=meta, body="")
        out = skill.execute(username="alice")

        assert captured["json"] == {"name": "alice"}
        assert out["results"][0]["status"] == 201
