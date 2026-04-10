import math

import pytest

from skills.math_eval import MathEvalSkill


@pytest.fixture
def skill():
    return MathEvalSkill()


class TestArithmetic:
    @pytest.mark.parametrize("expr,expected", [
        ("1+1", 2),
        ("2 * 3", 6),
        ("10 - 4", 6),
        ("10 / 4", 2.5),
        ("10 // 4", 2),
        ("10 % 3", 1),
        ("2 ** 8", 256),
        ("(1+2) * (3+4)", 21),
        ("-5", -5),
        ("+5", 5),
        ("--5", 5),
    ])
    def test_basic_ops(self, skill, expr, expected):
        assert skill.execute(expression=expr)["result"] == expected


class TestFunctions:
    def test_sqrt(self, skill):
        assert skill.execute(expression="sqrt(16)")["result"] == 4.0

    def test_trig_identity(self, skill):
        # sin^2 + cos^2 = 1
        out = skill.execute(expression="sin(0.7)**2 + cos(0.7)**2")
        assert out["result"] == pytest.approx(1.0)

    def test_log(self, skill):
        assert skill.execute(expression="log(e)")["result"] == pytest.approx(1.0)
        assert skill.execute(expression="log10(1000)")["result"] == pytest.approx(3.0)
        assert skill.execute(expression="log2(8)")["result"] == pytest.approx(3.0)

    def test_factorial(self, skill):
        assert skill.execute(expression="factorial(5)")["result"] == 120

    def test_min_max(self, skill):
        assert skill.execute(expression="max(1, 2, 3)")["result"] == 3
        assert skill.execute(expression="min(1, 2, 3)")["result"] == 1

    def test_constants(self, skill):
        assert skill.execute(expression="pi")["result"] == pytest.approx(math.pi)
        assert skill.execute(expression="tau")["result"] == pytest.approx(math.tau)
        assert skill.execute(expression="e")["result"] == pytest.approx(math.e)

    def test_nested(self, skill):
        out = skill.execute(expression="sqrt(2) * sin(pi/4) + 3**2")
        assert out["result"] == pytest.approx(10.0)


class TestSecurity:
    """The math_eval skill must reject anything that could escape the sandbox."""

    @pytest.mark.parametrize("expr", [
        '__import__("os")',
        "__import__",
        "open('/etc/passwd')",
        "exec('print(1)')",
        "eval('1+1')",
        "getattr(1, '__class__')",
        # attribute access not allowed
        "(1).__class__",
        "math.pi",
        # comprehensions not allowed
        "[x for x in range(10)]",
        # lambdas not allowed
        "(lambda: 1)()",
        # subscript not allowed
        "[1,2,3][0]",
        # comparison not allowed
        "1 < 2",
        # boolean ops not allowed
        "True and False",
        # name lookup of unknown identifier
        "foo",
        "os",
    ])
    def test_rejects_unsafe(self, skill, expr):
        out = skill.execute(expression=expr)
        assert "error" in out, f"Expected {expr!r} to be rejected, got: {out}"

    def test_rejects_string_constant(self, skill):
        # Only int/float constants are allowed
        out = skill.execute(expression="'hello'")
        assert "error" in out


class TestErrors:
    def test_div_by_zero(self, skill):
        out = skill.execute(expression="1/0")
        assert out["error"] == "division by zero"

    def test_empty(self, skill):
        assert "error" in skill.execute(expression="")
        assert "error" in skill.execute(expression="   ")

    def test_too_long(self, skill):
        out = skill.execute(expression="1+" * 300 + "1")
        assert "error" in out and "long" in out["error"]

    def test_syntax_error(self, skill):
        out = skill.execute(expression="1 + + + ")
        assert "error" in out


class TestSchema:
    def test_metadata(self, skill):
        assert skill.name == "math_eval"
        assert "expression" in skill.parameters
        assert skill.parameters["expression"]["required"] is True
