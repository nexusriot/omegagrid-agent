import hashlib

import pytest

from skills.hash_skill import HashSkill


@pytest.fixture
def skill():
    return HashSkill()


class TestAlgorithms:
    @pytest.mark.parametrize("algo", ["md5", "sha1", "sha256", "sha512"])
    def test_matches_hashlib(self, skill, algo):
        text = "the quick brown fox"
        out = skill.execute(text=text, algorithm=algo)
        expected = hashlib.new(algo, text.encode("utf-8")).hexdigest()
        assert out["hash"] == expected
        assert out["algorithm"] == algo
        assert out["input_length"] == len(text)

    def test_default_is_sha256(self, skill):
        out = skill.execute(text="hello")
        assert out["algorithm"] == "sha256"

    def test_unicode(self, skill):
        out = skill.execute(text="héllo 🚀", algorithm="sha256")
        expected = hashlib.sha256("héllo 🚀".encode("utf-8")).hexdigest()
        assert out["hash"] == expected

    def test_case_insensitive(self, skill):
        a = skill.execute(text="x", algorithm="SHA256")["hash"]
        b = skill.execute(text="x", algorithm="sha256")["hash"]
        assert a == b


class TestErrors:
    def test_unsupported_algorithm(self, skill):
        out = skill.execute(text="x", algorithm="sha999")
        assert "error" in out
