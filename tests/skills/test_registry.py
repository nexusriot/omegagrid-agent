"""Tests for SkillRegistry, especially the prompt-formatting code path which
previously crashed when a skill had string-valued parameter entries (the
`'str' object has no attribute 'get'` regression we fixed in this session).
"""
import pytest

from skills.base import BaseSkill
from skills.registry import SkillRegistry


class _DummySkill(BaseSkill):
    def __init__(self, name, parameters=None, description="d"):
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    def execute(self, **kwargs):
        return {"name": self.name, "args": kwargs}


@pytest.fixture
def registry():
    return SkillRegistry()


class TestRegister:
    def test_register_get(self, registry):
        s = _DummySkill("foo")
        registry.register(s)
        assert registry.get("foo") is s

    def test_get_missing(self, registry):
        assert registry.get("nope") is None

    def test_list_names(self, registry):
        registry.register(_DummySkill("a"))
        registry.register(_DummySkill("b"))
        assert sorted(registry.list_names()) == ["a", "b"]

    def test_unregister(self, registry):
        registry.register(_DummySkill("foo"))
        assert registry.unregister("foo") is True
        assert registry.get("foo") is None

    def test_unregister_missing(self, registry):
        assert registry.unregister("nope") is False

    def test_overwrite(self, registry):
        s1 = _DummySkill("foo", description="first")
        s2 = _DummySkill("foo", description="second")
        registry.register(s1)
        registry.register(s2)
        assert registry.get("foo").description == "second"


class TestDescribeForPrompt:
    def test_empty(self, registry):
        assert registry.describe_for_prompt() == ""

    def test_dict_params(self, registry):
        registry.register(_DummySkill("foo", parameters={
            "x": {"type": "string", "required": True},
            "y": {"type": "string", "required": False},
        }, description="does foo"))
        out = registry.describe_for_prompt()
        assert "foo(x (required), y (optional)): does foo" in out

    def test_string_params_do_not_crash(self, registry):
        """Regression: LLM-created skills sometimes have flat string params
        like {"city": "string"}. The registry must not crash on those."""
        registry.register(_DummySkill("foo", parameters={
            "city": "string",
            "country": "string",
        }, description="weather"))
        # Must not raise
        out = registry.describe_for_prompt()
        assert "foo(" in out
        assert "weather" in out

    def test_mixed_params(self, registry):
        registry.register(_DummySkill("mix", parameters={
            "a": {"type": "string", "required": True},
            "b": "string",
        }))
        out = registry.describe_for_prompt()
        assert "a (required)" in out
        # The string-valued one should not crash and should appear as optional
        assert "b (optional)" in out

    def test_includes_markdown_body(self, registry):
        s = _DummySkill("md", description="markdown skill")
        s.body = "step 1\nstep 2\nstep 3"
        registry.register(s)
        out = registry.describe_for_prompt()
        assert "step 1" in out
        assert "step 2" in out
