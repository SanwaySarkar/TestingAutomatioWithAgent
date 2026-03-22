# AI Agents V2 Documentation

## Overview

The `agents_v2.py` file implements 10 specialized AI agents that work together to process financial data through an ETL pipeline. These agents combine LLM intelligence with deterministic processing to ensure accuracy and reliability in financial data transformation.

## Agent Architecture

All agents inherit from `BaseAgent` which provides:
- Unified LLM router integration
- Consistent logging interface
- Standardized method signatures
- Shared utility functions

## Base Agent

### Properties
- `router`: LLM router instance for provider abstraction
- `NAME`: Class identifier for logging

### Methods
- `_llm()`: Call LLM with system and user prompts
- `_llm_json()`: Call LLM and parse JSON response
- `_log()`: Log messages with agent identifier

## Agent Implementations

### 1. SchemaAnalyzerAgent
**Purpose**: Analyze input data schema and classify columns

**Methods**:
- `analyze(columns, sample_rows)`: Classify columns using LLM
- `_fallback(columns, sample_rows)`: Heuristic classification when LLM unavailable

**Process**:
1. Send column names and sample data to LLM
2. Receive structured classification (semantic type, data type, etc.)
3. Fall back to heuristic analysis if LLM fails

### 2. RuleInterpreterAgent
**Purpose**: Convert English business rules to structured operations

**Methods**:
- `interpret(rules, input_columns)`: Interpret rules using LLM
- `_fallback(rules)`: Regex-based interpretation when LLM unavailable

**Supported Operations**:
- copy: Direct field copying
- multiply: Arithmetic multiplication
- subtract: Arithmetic subtraction
- divide: Arithmetic division
- add_constant: Add numeric constant
- db_lookup: Database value retrieval

### 3. ArithmeticPrecisionAgent
**Purpose**: Ensure arithmetic operations use BigDecimal precision

**Methods**:
- `validate_and_route(rules)`: Validate and tag arithmetic operations

**Process**:
1. Identify arithmetic operations (multiply, subtract, divide, add_constant)
2. Tag for BigDecimal processing
3. Flag missing operands or constants

### 4. DBMappingAgent
**Purpose**: Resolve database lookups for all input rows

**Methods**:
- `resolve(rules, input_rows, isin_column)`: Resolve DB lookups deterministically

**Process**:
1. Identify rules requiring database lookups
2. Extract ISIN from each input row
3. Query mock database for each (ISIN, key) combination
4. Return complete mapping dictionary

### 5. OutputMappingAgent
**Purpose**: Execute transformation rules to produce output rows

**Methods**:
- `execute(rules, input_rows, db_resolved, output_columns)`: Apply rules deterministically

**Process**:
1. Iterate through each input row
2. Apply each rule using appropriate operation
3. Use arithmetic_engine for precise calculations
4. Incorporate database lookup values
5. Ensure all output columns are populated

### 6. DriftDetectionAgent
**Purpose**: Detect systematic errors in input→output transformations

**Methods**:
- `detect(rules, output_rows, input_rows)`: Analyze for drift using LLM

**Process**:
1. Prepare input→output sample data
2. Send to LLM with rules for analysis
3. Receive drift detection report
4. Return structured results

### 7. RuleOptimizationAgent
**Purpose**: Suggest optimization opportunities for rule set

**Methods**:
- `optimize(rules)`: Recommend optimizations using LLM

**Process**:
1. Analyze rule operation distribution
2. Send to LLM for optimization suggestions
3. Provide fallback recommendations if LLM unavailable

### 8. TestGenerationAgent
**Purpose**: Generate and run test cases for validation

**Methods**:
- `generate(rules, sample_input, input_columns)`: Create test cases with LLM
- `run_tests(test_cases, output_rows, input_rows)`: Execute tests deterministically
- `_fallback(rules, sample)`: Generate basic test cases when LLM unavailable

**Process**:
1. Generate happy-path and edge-case tests per rule
2. Run tests against output data
3. Validate arithmetic operations use Decimal precision
4. Return pass/fail statistics

### 9. AnomalyDetectionAgent
**Purpose**: Identify statistical anomalies in output data

**Methods**:
- `detect(output_rows, rules)`: Find anomalies using LLM

**Process**:
1. Calculate statistics for output fields
2. Send to LLM for anomaly analysis
3. Return structured anomaly report
4. Include fallback for all-zero field detection

### 10. RuntimeTestValidatorAgent
**Purpose**: Validate Excel output cell-by-cell with expected values

**Methods**:
- `compute_expected(rules, input_rows, db_resolved, output_columns)`: Calculate expected values
- `validate_excel(excel_path, expected_rows, spec_map, output_columns, rules)`: Validate Excel file
- `_compare(actual, expected, op)`: Compare values with appropriate tolerance

**Process**:
1. Compute expected values for all cells deterministically
2. Generate human-readable specifications with LLM
3. Read actual Excel output
4. Compare each cell with expected value
5. Return detailed validation report

## Deterministic Components

Several agents operate without LLM involvement for reliability:
- ArithmeticPrecisionAgent: Rule validation
- DBMappingAgent: Database lookups
- OutputMappingAgent: Rule execution
- RuntimeTestValidatorAgent: Expected value calculation

## LLM Components

Agents that utilize LLMs for intelligent processing:
- SchemaAnalyzerAgent: Column classification
- RuleInterpreterAgent: Rule structuring
- DriftDetectionAgent: Error detection
- RuleOptimizationAgent: Optimization suggestions
- TestGenerationAgent: Test case generation
- AnomalyDetectionAgent: Statistical anomaly detection
- RuntimeTestValidatorAgent: Specification generation

## Error Handling

Each agent implements robust error handling:
- Graceful degradation to fallback methods
- Informative logging of issues
- Safe default values for missing data
- Continuation despite non-critical failures

## Integration Patterns

### LLM Usage
Agents consistently use the pattern:
1. Prepare system and user prompts
2. Call LLM through router
3. Parse structured responses
4. Fall back to deterministic alternatives

### Data Processing
Agents follow consistent data processing patterns:
1. Receive standardized input parameters
2. Return structured output dictionaries
3. Log operations with consistent formatting
4. Handle edge cases predictably

## Performance Considerations

- Batch processing for large rule sets
- Efficient data structures for lookups
- Minimal memory footprint
- Deterministic operations for speed
- Caching where beneficial

## Extensibility

The agent architecture facilitates extension:
- Standardized base class interface
- Consistent method signatures
- Modular design with single responsibilities
- Clear separation of LLM and deterministic operations
- Configurable through router parameters

## Testing Support

Agents are designed with testing in mind:
- Pure functions where possible
- Deterministic fallbacks for consistency
- Clear input/output contracts
- Comprehensive logging for debugging
- Isolated functionality per agent