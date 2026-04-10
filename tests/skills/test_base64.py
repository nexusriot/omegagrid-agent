import pytest

from skills.base64_skill import Base64Skill


@pytest.fixture
def skill():
    return Base64Skill()


class TestEncode:
    def test_basic(self, skill):
        out = skill.execute(action="encode", text="hello")
        assert out["action"] == "encode"
        assert out["output"] == "aGVsbG8="

    def test_unicode(self, skill):
        out = skill.execute(action="encode", text="héllo wörld 🚀")
        # Round-trip via decode
        round_trip = skill.execute(action="decode", text=out["output"])
        assert round_trip["output"] == "héllo wörld 🚀"

    def test_empty(self, skill):
        out = skill.execute(action="encode", text="")
        assert out["output"] == ""


class TestDecode:
    def test_basic(self, skill):
        out = skill.execute(action="decode", text="aGVsbG8=")
        assert out["output"] == "hello"

    def test_invalid_base64(self, skill):
        out = skill.execute(action="decode", text="not-valid-base64!@#$")
        assert "error" in out
        assert out["output"] is None


class TestErrors:
    def test_invalid_action(self, skill):
        out = skill.execute(action="bogus", text="x")
        assert "error" in out

    def test_action_case_insensitive(self, skill):
        out = skill.execute(action="ENCODE", text="hello")
        assert out["output"] == "aGVsbG8="
