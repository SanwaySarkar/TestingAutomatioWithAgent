"""
arithmetic_engine.py
Pure-Decimal deterministic computation engine.
AI NEVER touches this module. All math is exact BigDecimal.

Also contains parse_rule() — a regex/NLP rule parser that converts English
business rule text into a structured operation dict, handling:
  - Simple ops  : multiply, divide, subtract, add_constant, copy, db_lookup
  - Compound ops: any two ops chained with 'and'
    e.g. "Multiply price and nominal and divide result by brokerage" →
         expression = "(Price * Nominal) / Brokergage"
"""
from __future__ import annotations
import ast, re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, DivisionByZero
from typing import Any


# ── Rule parser ───────────────────────────────────────────────────────────────

def fuzzy_col(token: str, cols: list[str]) -> str | None:
    """
    Match a token extracted from rule text to the closest actual input column.
    Handles case differences, whitespace, underscores, and common typos
    (e.g. 'brokerage' matches column 'Brokergage').
    """
    if not token:
        return None
    t = token.strip().lower().replace(' ', '').replace('_', '')
    # Ignore placeholder words that mean "use previous result"
    if t in ('result', 'value', 'it', 'that', ''):
        return None
    # Exact normalised match
    for col in cols:
        if col.lower().replace(' ', '').replace('_', '') == t:
            return col
    # Substring match (either direction)
    for col in cols:
        c = col.lower().replace(' ', '').replace('_', '')
        if c in t or t in c:
            return col
    # Synonym / typo table
    syns = {'brokerage': 'brokergage', 'brokergage': 'brokerage',
            'fee': 'brokergage', 'charge': 'brokergage'}
    alt = syns.get(t)
    if alt:
        for col in cols:
            if alt in col.lower().replace(' ', '').replace('_', ''):
                return col
    return None


def _fmt(v: float) -> str:
    """Format a constant — strip trailing .0 for integer values."""
    return str(int(v)) if v == int(v) else str(v)


def _single(op: str, a: str | None, b: str | None) -> dict:
    _c = {'multiply': '*', 'divide': '/', 'subtract': '-', 'add': '+'}
    _s = {'multiply': '×', 'divide': '÷', 'subtract': '−', 'add': '+'}
    expr = f'{a} {_c[op]} {b}'
    return {'operation': op, 'operand_a': a, 'operand_b': b,
            'constant': None, 'expression': expr,
            'expression_str': f'{a} {_s[op]} {b} (4dp)'}


def _single_const(a: str | None, const: float) -> dict:
    cs = _fmt(const)
    return {'operation': 'add_constant', 'operand_a': a, 'operand_b': None,
            'constant': const, 'expression': f'{a} + {cs}',
            'expression_str': f'{a} + {cs} (4dp)'}


def _compound(op1: str, a1, b1, op2: str, a2, b2, const=None) -> dict:
    _c = {'multiply': '*', 'divide': '/', 'subtract': '-', 'add': '+'}
    _s = {'multiply': '×', 'divide': '÷', 'subtract': '−', 'add': '+'}
    # Build left-hand side from op1
    if op1 == 'add_constant':
        cs = _fmt(const)
        le = f'({a1} + {cs})'; lh = le
    else:
        le = f'({a1} {_c[op1]} {b1})'
        lh = f'({a1} {_s[op1]} {b1})'
    # Apply op2 to left result
    rhs = b2 or a2
    if op2 == 'add_constant':
        cs = _fmt(abs(const))
        sym = '+' if const >= 0 else '-'
        full_e = f'{le} {sym} {cs}'
        full_h = f'{lh} {sym} {cs} (4dp)'
    elif op2 == 'multiply':
        full_e = f'{le} * {rhs}'
        full_h = f'{lh} × {rhs} (4dp)'
    else:
        full_e = f'{le} {_c[op2]} {rhs}'
        full_h = f'{lh} {_s[op2]} {rhs} (4dp)'
    return {'operation': 'compound', 'operand_a': a1, 'operand_b': b1,
            'constant': const, 'expression': full_e, 'expression_str': full_h}


def parse_rule(rule_text: str, input_cols: list[str]) -> dict:
    """
    Parse an English arithmetic business rule into a structured operation dict.

    Handles both simple and compound (two-step) rules. Examples:

      Simple:
        "Multiply price and nominal and round to 4 decimal places"
        → {operation:'multiply', operand_a:'Price', operand_b:'Nominal',
           expression:'Price * Nominal'}

      Compound:
        "Multiply price and nominal and divide result by brokerage and round to 4 dp"
        → {operation:'compound', expression:'(Price * Nominal) / Brokergage'}

      Returns: dict with keys:
        operation      : copy|multiply|subtract|divide|add_constant|compound|db_lookup
        operand_a      : first input column name (or None)
        operand_b      : second input column name (or None)
        constant       : numeric constant (for add_constant) or None
        db_key         : KEY_N string (for db_lookup) or None
        expression     : machine-readable expression string e.g. "(Price * Nominal) / Brokergage"
        expression_str : human-readable spec e.g. "(Price × Nominal) ÷ Brokergage (4dp)"
    """
    txt = rule_text.strip().lower()
    txt = re.sub(r'\s+', ' ', txt)
    txt = re.sub(r'\s+and\s+round.*$', '', txt)
    txt = re.sub(r'\s+to\s+\d+\s+decimal.*$', '', txt)

    fc = lambda tok: fuzzy_col(tok, input_cols)   # shorthand

    # Patterns: most-specific (compound) first, single ops last
    PATTERNS = [
        # ── COMPOUND: 2 chained operations ───────────────────────────────────
        # multiply A and B and divide result by C
        (r'multiply\s+([\w\s]+?)\s+(?:and|by)\s+([\w\s]+?)\s+and\s+divide\s+(?:result\s+)?by\s+([\w\s]+?)$',
         lambda m: _compound('multiply', fc(m.group(1)), fc(m.group(2)),
                              'divide',   None,            fc(m.group(3)))),
        # multiply A and B and subtract C
        (r'multiply\s+([\w\s]+?)\s+(?:and|by)\s+([\w\s]+?)\s+and\s+subtract\s+([\w\s]+?)$',
         lambda m: _compound('multiply', fc(m.group(1)), fc(m.group(2)),
                              'subtract', None,            fc(m.group(3)))),
        # multiply A and B and add C
        (r'multiply\s+([\w\s]+?)\s+(?:and|by)\s+([\w\s]+?)\s+and\s+add\s+([\w\s]+?)$',
         lambda m: _compound('multiply', fc(m.group(1)), fc(m.group(2)),
                              'add',      None,            fc(m.group(3)))),
        # subtract B from A and divide result by C
        (r'subtract(?:ing)?\s+([\w\s]+?)\s+from\s+([\w\s]+?)\s+and\s+divide\s+(?:result\s+)?by\s+([\w\s]+?)$',
         lambda m: _compound('subtract', fc(m.group(2)), fc(m.group(1)),
                              'divide',   None,            fc(m.group(3)))),
        # divide A by B and subtract constant value N
        (r'divide\s+([\w\s]+?)\s+by\s+([\w\s]+?)\s+and\s+subtract\s+constant\s+value\s+(\d+(?:\.\d+)?)$',
         lambda m: _compound('divide', fc(m.group(1)), fc(m.group(2)),
                              'add_constant', None, None, const=-float(m.group(3)))),
        # divide A by B and subtract C
        (r'divide\s+([\w\s]+?)\s+by\s+([\w\s]+?)\s+and\s+subtract\s+([\w\s]+?)$',
         lambda m: _compound('divide', fc(m.group(1)), fc(m.group(2)),
                              'subtract', None, fc(m.group(3)))),
        # add constant N to A and multiply by B
        (r'add\s+constant\s+value\s+(\d+(?:\.\d+)?)\s+to\s+([\w\s]+?)\s+and\s+multiply\s+(?:by\s+)?([\w\s]+?)$',
         lambda m: _compound('add_constant', fc(m.group(2)), None,
                              'multiply', fc(m.group(3)), None, const=float(m.group(1)))),
        # ── SINGLE operations ─────────────────────────────────────────────────
        # multiply A and B  /  multiply A by B
        (r'multiply\s+([\w\s]+?)\s+(?:and|by)\s+([\w\s]+?)$',
         lambda m: _single('multiply', fc(m.group(1)), fc(m.group(2)))),
        # divide A by B
        (r'divide\s+([\w\s]+?)\s+by\s+([\w\s]+?)$',
         lambda m: _single('divide', fc(m.group(1)), fc(m.group(2)))),
        # subtract B from A  /  subtracting B from A
        (r'subtract(?:ing)?\s+([\w\s]+?)\s+from\s+([\w\s]+?)$',
         lambda m: _single('subtract', fc(m.group(2)), fc(m.group(1)))),
        # calculate net X by subtracting B from A
        (r'calculate\s+[\w\s]+?\s+by\s+subtract(?:ing)?\s+([\w\s]+?)\s+from\s+([\w\s]+?)$',
         lambda m: _single('subtract', fc(m.group(2)), fc(m.group(1)))),
        # add constant value N to X
        (r'add\s+constant\s+value\s+(\d+(?:\.\d+)?)\s+to\s+([\w\s]+?)$',
         lambda m: _single_const(fc(m.group(2)), float(m.group(1)))),
        # add constant value N  (no 'to X' — use first col)
        (r'add\s+constant\s+value\s+(\d+(?:\.\d+)?)$',
         lambda m: _single_const(input_cols[0] if input_cols else None, float(m.group(1)))),
    ]

    for pattern, builder in PATTERNS:
        m = re.search(pattern, txt)
        if m:
            return builder(m)

    # DB lookup
    if re.search(r'fetch|database|key_\d+', txt):
        key = re.search(r'key_(\d+)', txt)
        return {'operation': 'db_lookup', 'operand_a': None, 'operand_b': None,
                'constant': None, 'db_key': f'KEY_{key.group(1)}' if key else None,
                'expression': None, 'expression_str': 'DB lookup'}

    # Copy / passthrough
    src = input_cols[0] if input_cols else None
    return {'operation': 'copy', 'operand_a': src, 'operand_b': None,
            'constant': None, 'db_key': None,
            'expression': None, 'expression_str': f'copy {src}'}


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


def compute_compound(expression: str, row: dict) -> str:
    """
    Execute a compound expression like '(Price * Nominal) / Brokergage'
    against a data row dict using pure BigDecimal arithmetic.
    Column name references in the expression are resolved from the row dict.
    """
    return compute_expr(expression, row)
