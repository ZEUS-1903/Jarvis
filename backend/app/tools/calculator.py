"""A safe calculator.

Why not eval(): the expression comes from the LLM, which may be echoing text an
attacker controls. eval("__import__('os').system('rm -rf ~')") would run it.
Instead we parse into an AST (a tree of operations) and evaluate ONLY node
types we explicitly allow. Anything else is rejected before it runs.
"""
import ast
import math
import operator
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolError

_BINARY_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {"sqrt": math.sqrt, "abs": abs, "round": round,
              "log": math.log, "log10": math.log10}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_MAX_RESULT_BITS = 10_000  # stops 9**9**9-style CPU/memory bombs


class CalcArgs(BaseModel):
    expression: str = Field(
        max_length=200,
        description="Arithmetic expression, e.g. '(1200 * 0.15) + 40' or 'sqrt(2) * 3'. "
        "Supports + - * / // % **, parentheses, sqrt, abs, round, log, log10, pi, e.",
    )


def _eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    # bool is a subclass of int in Python; exclude it explicitly.
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(left, int) and isinstance(right, int):
            # Estimate result size BEFORE computing it.
            if abs(right) > 1 and max(abs(left), 1).bit_length() * abs(right) > _MAX_RESULT_BITS:
                raise ToolError("result too large")
        return _BINARY_OPS[type(node.op)](left, right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
    ):
        return _FUNCTIONS[node.func.id](*(_eval(arg) for arg in node.args))
    raise ToolError(f"unsupported expression element: {type(node).__name__}")


class CalculatorTool(Tool):
    name = "calculate"
    description = (
        "Evaluate an arithmetic expression exactly. Use for any non-trivial math "
        "instead of computing it yourself."
    )
    input_model = CalcArgs
    timeout_s = 1.0

    async def run(self, args: CalcArgs) -> dict[str, Any]:
        try:
            tree = ast.parse(args.expression, mode="eval")
        except SyntaxError:
            raise ToolError("could not parse expression")
        try:
            value = _eval(tree)
        except ZeroDivisionError:
            raise ToolError("division by zero")
        except (OverflowError, ValueError, TypeError) as exc:
            raise ToolError(f"math error: {exc}")
        if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
            value = int(value)  # 4.0 -> 4 reads better in answers
        return {"expression": args.expression, "result": value}
