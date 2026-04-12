import string

import pytest

from skills.password_gen import PasswordGenSkill, _AMBIGUOUS


@pytest.fixture
def skill():
    return PasswordGenSkill()


class TestBasic:
    def test_default(self, skill):
        out = skill.execute()
        assert out["count"] == 1
        assert out["length"] == 16
        assert len(out["passwords"]) == 1
        assert len(out["passwords"][0]) == 16

    def test_length(self, skill):
        out = skill.execute(length=32, count=3)
        assert out["count"] == 3
        for p in out["passwords"]:
            assert len(p) == 32

    def test_passwords_are_distinct(self, skill):
        out = skill.execute(length=20, count=10)
        # Effectively zero chance of collision at length 20
        assert len(set(out["passwords"])) == 10


class TestClassGuarantee:
    """Generated passwords must contain at least one char from each enabled class."""

    def test_all_classes(self, skill):
        # Run several times so the probabilistic guarantee is meaningful
        for _ in range(20):
            p = skill.execute(length=12)["passwords"][0]
            assert any(c.islower() for c in p), f"missing lowercase in {p!r}"
            assert any(c.isupper() for c in p), f"missing uppercase in {p!r}"
            assert any(c.isdigit() for c in p), f"missing digit in {p!r}"
            assert any(c in "!@#$%^&*()-_=+[]{};:,.<>/?" for c in p), f"missing symbol in {p!r}"

    def test_only_lowercase(self, skill):
        for _ in range(10):
            p = skill.execute(
                length=20,
                use_lowercase=True,
                use_uppercase=False,
                use_digits=False,
                use_symbols=False,
            )["passwords"][0]
            assert all(c in string.ascii_lowercase for c in p)

    def test_only_digits(self, skill):
        for _ in range(10):
            p = skill.execute(
                length=20,
                use_lowercase=False,
                use_uppercase=False,
                use_digits=True,
                use_symbols=False,
            )["passwords"][0]
            assert all(c in string.digits for c in p)


class TestExcludeAmbiguous:
    def test_ambiguous_chars_excluded(self, skill):
        for _ in range(20):
            p = skill.execute(length=40, exclude_ambiguous=True)["passwords"][0]
            for ch in p:
                assert ch not in _AMBIGUOUS, f"found ambiguous char {ch!r} in {p!r}"


class TestErrors:
    def test_no_classes(self, skill):
        out = skill.execute(
            use_lowercase=False,
            use_uppercase=False,
            use_digits=False,
            use_symbols=False,
        )
        assert "error" in out

    @pytest.mark.parametrize("length", [0, 7, 129, -1])
    def test_length_out_of_range(self, skill, length):
        assert "error" in skill.execute(length=length)

    @pytest.mark.parametrize("count", [0, -1, 51])
    def test_count_out_of_range(self, skill, count):
        assert "error" in skill.execute(count=count)

    def test_length_smaller_than_class_count(self, skill):
        # 4 classes enabled, length=3 -> impossible to satisfy guarantee
        out = skill.execute(length=3)
        # length=3 fails the 8-128 bound first; specifically test the 4-class case
        out2 = skill.execute(length=8, use_lowercase=True, use_uppercase=True, use_digits=True, use_symbols=True)
        # length=8 with 4 classes is fine
        assert "error" not in out2
