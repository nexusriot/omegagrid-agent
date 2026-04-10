from __future__ import annotations

import ast
import math
import operator
from typing import Any, Dict

from skills.base import BaseSkill


# Whitelisted binary, unary, and boolean operators
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Whitelisted math functions and constants
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "pow": math.pow,
    "exp": math.exp,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "ceil": math.ceil,
    "floor": math.floor,
    "fabs": math.fabs,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "factorial": math.factorial,
    "degrees": math.degrees,
    "radians": math.radians,
    "gcd": math.gcd,
    "hypot": math.hypot,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.Num):  # py<3.8 fallback
        return node.n
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError(f"Operator {op_type.__name__} not allowed")
        return _BIN_OPS[op_type](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unary operator {op_type.__name__} not allowed")
        return _UNARY_OPS[op_type](_eval_node(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown identifier: {node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function calls are allowed")
        fname = node.func.id
        if fname not in _FUNCTIONS:
            raise ValueError(f"Function not allowed: {fname}")
        args = [_eval_node(a) for a in node.args]
        return _FUNCTIONS[fname](*args)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


class MathEvalSkill(BaseSkill):
    """Safely evaluate arithmetic expressions using AST (no eval())."""

    name = "math_eval"
    description = (
        "Safely evaluate a math expression. Supports +, -, *, /, //, %, **, "
        "parentheses, and functions: sqrt, log, log2, log10, exp, sin, cos, tan, "
        "asin, acos, atan, atan2, ceil, floor, fabs, abs, round, min, max, "
        "factorial, degrees, radians, gcd, hypot, pow. Constants: pi, e, tau, inf."
    )
    parameters = {
        "expression": {
            "type": "string",
            "description": "Math expression to evaluate, e.g. 'sqrt(2) * sin(pi/4) + 3**2'",
            "required": True,
        },
    }

    def execute(self, expression: str = "", **kwargs) -> Dict[str, Any]:
        expr = (expression or "").strip()
        if not expr:
            return {"error": "expression is required"}
        if len(expr) > 500:
            return {"error": "expression too long (max 500 chars)"}
        try:
            tree = ast.parse(expr, mode="eval")
            result = _eval_node(tree)
        except ZeroDivisionError:
            return {"error": "division by zero", "expression": expr}
        except (ValueError, TypeError, OverflowError, SyntaxError) as e:
            return {"error": str(e), "expression": expr}
        return {"expression": expr, "result": result}
