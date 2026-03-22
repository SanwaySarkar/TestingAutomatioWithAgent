# Arithmetic Engine Documentation

## Overview

The `arithmetic_engine.py` file provides a pure-decimal deterministic computation engine for financial calculations. This module ensures all mathematical operations use exact BigDecimal precision, eliminating floating-point errors that could affect financial data accuracy.

## Key Features

- **Pure Decimal Operations**: All calculations use Python's `Decimal` type for exact precision
- **Deterministic Results**: Same inputs always produce identical outputs
- **No AI Involvement**: Mathematical operations are completely deterministic
- **Financial Precision**: Specifically designed for 4-decimal-place financial calculations
- **Expression Evaluation**: Supports complex arithmetic expressions with field references

## Core Functions

### `to_decimal(v)`
Converts any value to a Decimal with proper error handling.
- Strips whitespace from string inputs
- Returns Decimal("0") for invalid inputs
- Handles various input types (int, float, string, etc.)

### `round4(v)`
Rounds a Decimal to 4 decimal places and returns as string.
- Uses ROUND_HALF_UP rounding strategy
- Ensures consistent financial precision

### `_resolve_expr(expr, ctx)`
Tokenizes and evaluates arithmetic expressions with field references.
- Replaces field names with Decimal values from context
- Supports basic arithmetic operators (+, -, *, /)
- Handles parentheses for operation precedence
- Returns Decimal("0") for syntax errors or invalid operations

### `compute_multiply(a, b)`
Multiplies two values with 4-decimal precision.
- Converts inputs to Decimal
- Performs multiplication
- Rounds result to 4 decimals

### `compute_subtract(a, b)`
Subtracts second value from first with 4-decimal precision.
- Converts inputs to Decimal
- Performs subtraction
- Rounds result to 4 decimals

### `compute_divide(a, b)`
Divides first value by second with 4-decimal precision.
- Converts inputs to Decimal
- Handles division by zero (returns "0.0000")
- Performs division
- Rounds result to 4 decimals

### `compute_add_constant(a, constant)`
Adds a constant to a value with 4-decimal precision.
- Converts inputs to Decimal
- Performs addition
- Rounds result to 4 decimals

### `compute_expr(expr, ctx)`
Evaluates a mathematical expression with field references.
- Uses `_resolve_expr` for parsing and evaluation
- Rounds result to 4 decimals

## Implementation Details

### Decimal Precision
All operations use Python's `decimal.Decimal` type which provides:
- Exact decimal representation (no binary floating-point errors)
- Configurable precision and rounding
- Predictable behavior for financial calculations

### Rounding Strategy
Uses `ROUND_HALF_UP` which rounds 0.5 up to 1:
- Consistent with financial rounding standards
- Matches expectations for monetary calculations

### Error Handling
The engine gracefully handles various error conditions:
- Invalid input values default to Decimal("0")
- Division by zero returns "0.0000"
- Syntax errors in expressions return Decimal("0")
- Type conversion errors default to safe values

### Expression Parser
The `_resolve_expr` function provides a secure expression evaluator:
- Tokenizes expressions on whitespace and operators
- Replaces field references with context values
- Builds AST (Abstract Syntax Tree) for evaluation
- Prevents code injection by restricting operations
- Supports nested parentheses for complex calculations

## Usage Examples

```python
from arithmetic_engine import compute_multiply, compute_add_constant

# Basic operations
result1 = compute_multiply("10.50", "2.00")  # Returns "21.0000"
result2 = compute_add_constant("100.00", "15.75")  # Returns "115.7500"

# Expression evaluation
context = {"price": "10.50", "quantity": "2.00", "tax_rate": "0.08"}
expr = "price * quantity * (1 + tax_rate)"
result3 = compute_expr(expr, context)  # Returns calculated value
```

## Security Considerations

The expression evaluator:
- Uses AST parsing for safe evaluation
- Restricts operations to basic arithmetic
- Prevents arbitrary code execution
- Sanitizes input field names and values
- Handles all errors gracefully without crashing

## Performance Characteristics

- Fast execution for individual operations
- Minimal memory overhead
- No external dependencies
- Deterministic timing (important for testing)
- Efficient Decimal operations for financial precision

## Integration with ETL Pipeline

The arithmetic engine integrates with the ETL pipeline:
- Used by OutputMappingAgent for rule execution
- Used by RuntimeTestValidatorAgent for expected value calculation
- Ensures consistency between in-memory calculations and Excel output
- Provides audit trail for all mathematical operations