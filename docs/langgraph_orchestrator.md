# LangGraph Orchestrator Documentation

## Overview

The `langgraph_orchestrator.py` file implements a sophisticated Investment ETL (Extract, Transform, Load) pipeline using LangGraph principles. It orchestrates 10 specialized AI agents to process financial data, applying business rules to transform input data into validated output.

## Architecture

The orchestrator follows a LangGraph state machine pattern with 10 sequential agents:

```
START → schema_analyzer → rule_interpreter → precision_guard
     → db_mapping → output_mapping → drift_detection
     → rule_optimizer → test_generator → anomaly_detector
     → excel_writer → runtime_validator → [conditional: pass?]
                                          ↓ FAIL
                                    rule_optimizer (re-run)
                                          ↓
                                        END
```

## State Management

The orchestrator uses an `ETLState` class that extends `AgentState` to maintain the complete pipeline state. Each agent receives the full state dictionary and returns a partial dictionary containing only the keys it modifies. LangGraph automatically merges these updates.

Key state elements include:
- Configuration (input files, provider, model)
- Data (input columns, rows, output columns, rules)
- Agent outputs (schema, interpreted rules, DB mappings, etc.)
- Control flow variables (drift detection, validation results, retry count)

## Agent Pipeline

### 1. Schema Analyzer (`node_schema_analyzer`)
Analyzes input column names and sample data to classify each column's semantic type, data type, nullability, and description.

### 2. Rule Interpreter (`node_rule_interpreter`)
Converts English business rules from Excel mapping to structured operations (copy, multiply, subtract, divide, add_constant, db_lookup).

### 3. Precision Guard (`node_precision_guard`)
Ensures arithmetic operations use BigDecimal precision and flags potential issues.

### 4. DB Mapping (`node_db_mapping`)
Resolves database lookups for all rows and lookup fields using the mock database.

### 5. Output Mapping (`node_output_mapping`)
Executes all rules deterministically to produce output rows.

### 6. Drift Detection (`node_drift_detection`)
Detects systematic errors in input→output transformations.

### 7. Rule Optimizer (`node_rule_optimizer`)
Suggests optimization opportunities for the rule set.

### 8. Test Generator (`node_test_generator`)
Generates and runs test cases for rule validation.

### 9. Anomaly Detector (`node_anomaly_detector`)
Identifies statistical anomalies in the output data.

### 10. Excel Writer (`node_excel_writer`)
Writes the output data to Excel format.

### 11. Runtime Validator (`node_runtime_validator`)
Computes expected values and validates the Excel output cell-by-cell.

### 12. Excel Rewriter (`node_excel_rewriter`)
Rewrites the Excel file with validation highlights.

### 13. Final Report (`node_final_report`)
Prints the pipeline completion summary.

## Conditional Routing

The orchestrator implements conditional routing after two key nodes:

1. After drift detection: Always continues to rule optimizer
2. After runtime validation: Routes to rewriter if pass, or retry loop if fail (with max retries)

## Deterministic Components

Several components operate without LLM involvement for reliability:
- File loading (`node_loader`)
- Arithmetic precision guard
- Database mapping
- Output mapping (rule execution)
- Excel writing
- Runtime validation

## LLM Components

Components that utilize LLMs for intelligent processing:
- Schema analysis
- Rule interpretation
- Drift detection
- Rule optimization
- Test generation
- Anomaly detection
- Runtime specification generation

## Excel Output

The orchestrator generates a comprehensive Excel workbook with multiple sheets:
1. Output_Data: Main transformed data with color-coded cells
2. Validation_Report: Cell-by-cell validation results
3. LangGraph_Flow: Visual representation of the execution flow
4. Audit_Report: Complete execution audit trail

## Usage

```bash
python langgraph_orchestrator.py --input data.xlsx --rules rules.xlsx --provider gemini
```

## Dependencies

- pandas: Excel file processing
- openpyxl: Excel file creation and manipulation
- Native LangChain/LangGraph implementations (lc_core.py, lg_graph.py)
- Arithmetic engine (arithmetic_engine.py)
- Mock database (mock_db.py)