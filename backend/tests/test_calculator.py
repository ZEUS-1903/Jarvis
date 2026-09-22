import pytest

from app.tools.calculator import CalcArgs, CalculatorTool
from app.tools.base import ToolError

calc = CalculatorTool()


async def run(expr: str):
    return (await calc.run(CalcArgs(expression=expr)))["result"]


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("2 + 3 * 4", 14),
        ("(1200 * 0.15) + 40", 220),
        ("-2 ** 2", -4),          # Python precedence: -(2**2)
        ("7 // 2", 3),
        ("7 % 3", 1),
        ("sqrt(16)", 4),
        ("round(pi, 2)", 3.14),
        ("10 / 4", 2.5),
    ],
)
async def test_valid_expressions(expr, expected):
    assert await run(expr) == expected


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo pwned')",  # code execution attempt
        "open('/etc/passwd').read()",
        "(1).__class__",                           # attribute access
        "[1, 2, 3]",
        "x + 1",                                   # unknown name
        "True + 1",                                # bools are not numbers here
        "9 ** 9 ** 9",                             # CPU/memory bomb
        "1 / 0",
        "sqrt(-1)",
        "2 +",
    ],
)
async def test_rejected_expressions(expr):
    with pytest.raises(ToolError):
        await run(expr)
