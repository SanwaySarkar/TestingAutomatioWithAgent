"""
arithmetic_engine.py
Pure-Decimal deterministic computation engine.
AI NEVER touches this module. All math is exact BigDecimal.
"""
from __future__ import annotations
import ast, re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, DivisionByZero
from typing import Any


def to_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, TypeError):
        return Decimal("0")


def round4(v: Decimal) -> str:
    """Round to 4 decimal places, return as string."""
    return str(v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _resolve_expr(expr: str, ctx: dict) -> Decimal:
    """
    Tokenise expression, replace field refs with Decimal values,
    then evaluate via AST walk — no float ever used.
    """
    tokens = re.split(r"(\s+|[+\-*/()])", expr)
    parts = []
    for tok in tokens:
        t = tok.strip()
        if not t:
            continue
        if re.match(r"^[+\-*/()]$", t):
            parts.append(t)
        elif re.match(r"^-?\d+(\.\d+)?$", t):
            parts.append(t)
        elif t in ctx:
            parts.append(str(to_decimal(ctx[t])))
        else:
            parts.append("0")

    flat = " ".join(parts)
    if not flat.strip():
        return Decimal("0")

    try:
        tree = ast.parse(flat, mode="eval")
    except SyntaxError:
        return Decimal("0")

    def visit(node) -> Decimal:
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant):   return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if isinstance(node, ast.BinOp):
            l, r = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):  return l + r
            if isinstance(node.op, ast.Sub):  return l - r
            if isinstance(node.op, ast.Mult): return l * r
            if isinstance(node.op, ast.Div):
                try:    return l / r
                except (DivisionByZero, InvalidOperation): return Decimal("0")
        return Decimal("0")

    try:
        return visit(tree)
    except Exception:
        return Decimal("0")


# ── Public compute functions ──────────────────────────────────────────────────

def compute_multiply(a: Any, b: Any) -> str:
    return round4(to_decimal(a) * to_decimal(b))

def compute_subtract(a: Any, b: Any) -> str:
    return round4(to_decimal(a) - to_decimal(b))

def compute_divide(a: Any, b: Any) -> str:
    bd = to_decimal(b)
    if bd == Decimal("0"):
        return "0.0000"
    return round4(to_decimal(a) / bd)

def compute_add_constant(a: Any, constant: Any) -> str:
    return round4(to_decimal(a) + to_decimal(constant))

def compute_expr(expr: str, ctx: dict) -> str:
    return round4(_resolve_expr(expr, ctx))
