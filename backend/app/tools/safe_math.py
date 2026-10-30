"""Deterministic, sandbox-free expression evaluator (AST allowlist). No eval/exec of user text."""
from __future__ import annotations

import ast
import math
import operator as op

_BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow}
_UN = {ast.UAdd: op.pos, ast.USub: op.neg}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
          "log10": math.log10, "exp": math.exp, "abs": abs, "round": round, "floor": math.floor,
          "ceil": math.ceil, "factorial": math.factorial}
_NAMES = {"pi": math.pi, "e": math.e}
MAX_LEN, MAX_NODES = 200, 60


class MathError(ValueError):
    pass


def safe_eval(expr: str) -> float | int:
    if len(expr) > MAX_LEN:
        raise MathError("Expression too long")
    try:
        tree = ast.parse(expr.strip().replace("^", "**"), mode="eval")
    except SyntaxError:
        raise MathError("Invalid expression")
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise MathError("Expression too complex")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name) and n.id in _NAMES:
            return _NAMES[n.id]
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow):
                if abs(b) > 1000 or (abs(a) > 1 and abs(b) * math.log10(abs(a)) > 300):
                    raise MathError("Exponent too large")
            try:
                return _BIN[type(n.op)](a, b)
            except ZeroDivisionError:
                raise MathError("Division by zero")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            args = [ev(a) for a in n.args]
            if n.func.id == "factorial" and (not isinstance(args[0], int) or args[0] > 500):
                raise MathError("factorial argument out of range")
            try:
                return _FUNCS[n.func.id](*args)
            except (ValueError, TypeError, OverflowError):
                raise MathError("Math domain error")
        raise MathError("Unsupported expression element")

    result = ev(tree)
    if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
        raise MathError("Result is not a finite number")
    return result
