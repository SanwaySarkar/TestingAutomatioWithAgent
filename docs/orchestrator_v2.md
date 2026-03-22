# Orchestrator V2 Documentation

## Overview

The `orchestrator_v2.py` file implements a generic Investment ETL (Extract, Transform, Load) pipeline that orchestrates 10 AI agents to process financial data. Unlike the LangGraph version, this orchestrator uses a sequential execution model with the LLM router for provider flexibility.

## Key Features

- **Multi-Provider Support**: Works with Claude, Gemini, and Ollama
- **Fallback Chains**: Automatic fallback to alternative providers
- **Deterministic Processing**: Critical operations use exact BigDecimal arithmetic
- **Comprehensive Validation**: Multi-layer validation of results
- **Rich Excel Output**: Detailed reports with color-coded validation

## Architecture

The orchestrator follows a linear 10-agent pipeline:

1. SchemaAnalyzerAgent - Analyze input data schema
2. RuleInterpreterAgent - Convert English rules to structured operations
3. ArithmeticPrecisionAgent - Validate arithmetic operations
4. DBMappingAgent - Resolve database lookups
5. OutputMappingAgent - Execute transformation rules
6. DriftDetectionAgent - Detect systematic errors
7. RuleOptimizationAgent - Suggest rule improvements
8. TestGenerationAgent - Generate and run test cases
9. AnomalyDetectionAgent - Identify statistical anomalies
10. RuntimeTestValidatorAgent - Validate Excel output cell-by-cell

## Main Components

### File Processing
- `read_rule_mapping()`: Parse Excel rule mapping files
- `read_input_data()`: Load input Excel data
- `write_excel_output()`: Generate comprehensive Excel reports

### Helper Functions
- `banner()`: Display formatted section headers
- `_is_number()`: Check if string represents a number

## Agent Pipeline Execution

### Agent 1: Schema Analyzer
Analyzes column names and sample data to classify each column's properties using LLM intelligence.

### Agent 2: Rule Interpreter
Converts English business rules to structured operations using LLM understanding.

### Agent 3: Arithmetic Precision Guard
Ensures arithmetic operations use BigDecimal precision and flags potential issues.

### Agent 4: DB Mapping
Resolves database lookups for all rows using the mock database.

### Agent 5: Output Mapping
Executes all transformation rules deterministically to produce output rows.

### Agent 6: Drift Detection
Uses LLM to detect systematic errors in input→output transformations.

### Agent 7: Rule Optimization
Suggests optimization opportunities for the rule set using LLM analysis.

### Agent 8: Test Generation
Generates test cases with LLM and runs them deterministically.

### Agent 9: Anomaly Detection
Identifies statistical anomalies in output data using LLM analysis.

### Agent 10: Runtime Test Validator
Computes expected values and validates Excel output cell-by-cell.

## Excel Output Generation

The orchestrator creates a comprehensive Excel workbook with multiple sheets:

1. **Output_Data**: Main transformed data with color-coded cells
   - Yellow: Direct copy from input
   - Light green: Database lookup values
   - Light blue: Calculated values
   - Red: Validation failures
   - Green: Validation passes

2. **Validation_Report**: Cell-by-cell validation results
   - Summary statistics
   - Detailed failure analysis
   - Pass/fail indicators

3. **Rule_Summary**: Complete rule mapping with specifications
   - Operation types
   - Operand details
   - Precision requirements

4. **Audit_Report**: Complete execution audit trail
   - Timestamp and configuration
   - Provider information
   - Processing statistics
   - Validation results

5. **Legend**: Color coding explanation

## LLM Router Integration

The orchestrator uses `LLMRouter` for flexible provider selection:
- Primary provider selection
- Configurable fallback chains
- Automatic provider health checks
- Consistent API across providers

## Usage

### Command Line Interface
```bash
python orchestrator_v2.py \
  --input path/to/data.xlsx \
  --rules path/to/rules.xlsx \
  --out path/to/output.xlsx \
  --provider gemini \
  --model gemini-2.0-flash \
  --fallback claude
```

### Programmatic Usage
```python
from orchestrator_v2 import run

audit = run(
    input_file="data.xlsx",
    rule_file="rules.xlsx",
    out_path="output.xlsx",
    provider="claude"
)
```

## Configuration Options

### Primary Parameters
- `input_file`: Path to input Excel data file
- `rule_file`: Path to rule mapping Excel file
- `out_path`: Path for output Excel file
- `provider`: Primary LLM provider (claude/gemini/ollama)
- `model`: Specific model name for primary provider

### Fallback Configuration
- `fallback`: Secondary LLM provider
- `fallback_model`: Specific model name for fallback provider
- `ollama_host`: Ollama server URL

## Validation Process

The orchestrator implements multi-layer validation:

1. **In-Memory Tests**: Generated test cases run on output data
2. **Excel Draft**: Initial Excel file written before validation
3. **Cell-by-Cell Validation**: Runtime validator computes expected values
4. **Highlighting**: Final Excel includes color-coded validation results

## Error Handling

The orchestrator includes robust error handling:
- Graceful degradation when LLMs are unavailable
- Fallback to heuristic processing for critical functions
- Comprehensive logging of all operations
- Detailed error reporting in audit trail
- Continuation despite non-critical failures

## Performance Considerations

- Sequential execution model for simplicity
- Deterministic operations for speed
- Efficient Excel processing with openpyxl
- Memory-conscious batch processing for large rule sets
- Caching of intermediate results where beneficial

## Extensibility

The design facilitates extension:
- Modular agent architecture
- Standardized agent interface
- Configurable provider system
- Pluggable validation components
- Customizable output formatting

## Dependencies

- pandas: Excel file processing
- openpyxl: Excel file creation and manipulation
- llm_router: Multi-provider LLM interface
- agents_v2: AI agent implementations
- arithmetic_engine: Deterministic calculations
- mock_db: Database simulation