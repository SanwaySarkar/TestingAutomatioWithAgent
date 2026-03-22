# AgenticAIExcel - Investment ETL Pipeline

## Overview

AgenticAIExcel is a sophisticated Investment ETL (Extract, Transform, Load) pipeline that processes financial data using AI agents. The system transforms input data according to business rules defined in Excel spreadsheets, leveraging multiple LLM providers for intelligent processing while ensuring deterministic calculations for financial accuracy.

## Features

- **Multi-Provider LLM Support**: Works with Claude, Gemini, and Ollama
- **Deterministic Calculations**: Financial arithmetic uses exact BigDecimal precision
- **Comprehensive Validation**: Multi-layer validation of results
- **Rich Excel Output**: Detailed reports with color-coded validation
- **Fallback Mechanisms**: Automatic switching between LLM providers
- **Stateful Processing**: LangGraph-based orchestrator with checkpointing

## Architecture

The system implements two orchestrators:

1. **LangGraph Orchestrator** (`langgraph_orchestrator.py`) - Advanced stateful workflow
2. **Sequential Orchestrator** (`orchestrator_v2.py`) - Linear agent execution

Both orchestrators use the same 10 AI agents for processing:
1. Schema Analyzer - Analyze input data schema
2. Rule Interpreter - Convert English rules to structured operations
3. Precision Guard - Ensure arithmetic precision
4. DB Mapping - Resolve database lookups
5. Output Mapping - Execute transformation rules
6. Drift Detection - Detect systematic errors
7. Rule Optimizer - Suggest rule improvements
8. Test Generator - Generate and run test cases
9. Anomaly Detector - Identify statistical anomalies
10. Runtime Validator - Validate Excel output cell-by-cell

## Requirements

- Python 3.8+
- Virtual environment (recommended)
- LLM API keys (depending on chosen provider)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd AgenticAIExcel
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

Depending on the LLM provider you choose, you may need to set API keys:

- **Claude**: Install the `anthropic` package (`pip install anthropic`)
- **Gemini**: Set `GEMINI_API_KEY` environment variable
- **Ollama**: Run Ollama locally (no API key required)

Setting environment variables:
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your-api-key-here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your-api-key-here

# macOS/Linux
export GEMINI_API_KEY=your-api-key-here
```

## Usage

### LangGraph Orchestrator (Recommended)

```bash
python langgraph_orchestrator.py --input data.xlsx --rules rules.xlsx --provider gemini
```

Full parameter list:
```bash
python langgraph_orchestrator.py \
  --input path/to/input.xlsx \
  --rules path/to/rules.xlsx \
  --out path/to/output.xlsx \
  --provider claude|gemini|ollama \
  --model specific-model-name \
  --stream \
  --thread-id etl-run-identifier
```

### Sequential Orchestrator

```bash
python orchestrator_v2.py --input data.xlsx --rules rules.xlsx --provider gemini
```

Full parameter list:
```bash
python orchestrator_v2.py \
  --input path/to/input.xlsx \
  --rules path/to/rules.xlsx \
  --out path/to/output.xlsx \
  --provider claude|gemini|ollama \
  --model specific-model-name \
  --fallback fallback-provider \
  --fallback-model fallback-model-name
```

## Provider-Specific Instructions

### Claude (Anthropic)
1. Install the anthropic package: `pip install anthropic`
2. The system will automatically detect if the package is available
3. No API key required in the code (handled by the anthropic package)

### Gemini (Google)
1. Obtain a Gemini API key from Google AI Studio
2. Set the `GEMINI_API_KEY` environment variable
3. Example: `export GEMINI_API_KEY=AIzaSyAe-GKKhFOuNrWRjCVWh-xBsxdpg8XGC-Q`

### Ollama (Local)
1. Download and install Ollama from https://ollama.ai
2. Run Ollama: `ollama serve`
3. Pull a model: `ollama pull qwen3-coder:30b` (or any other supported model)
4. The system will automatically detect if Ollama is running

## Input Files Format

### Input Data (data.xlsx)
- First row contains column headers
- Subsequent rows contain data to be processed
- Columns should match the field names referenced in rules

### Rule Mapping (rules.xlsx)
- Defines transformation rules from input to output
- Contains English descriptions of business rules
- Specifies operations like copy, multiply, subtract, etc.

## Output Files

The system generates a comprehensive Excel workbook with multiple sheets:

1. **Output_Data**: Main transformed data with color-coded cells
2. **Validation_Report**: Cell-by-cell validation results
3. **Rule_Summary**: Complete rule mapping with specifications
4. **Audit_Report**: Complete execution audit trail
5. **LangGraph_Flow**: Visual representation of the execution flow (LangGraph only)
6. **Legend**: Color coding explanation

## Error Handling

The system implements robust error handling:
- Graceful degradation when LLMs are unavailable
- Fallback to heuristic processing for critical functions
- Comprehensive logging of all operations
- Detailed error reporting in audit trail
- Continuation despite non-critical failures

## Troubleshooting

### No LLM Available
If you see exceptions about LLMs not being available:
1. Check that you've set the required environment variables
2. Verify that required packages are installed
3. Confirm that local services (like Ollama) are running
4. Try a different provider using the `--provider` flag

### ImportError: No module named 'langchain_core_impl'
This error occurs when the system tries to import from the wrong module. The project includes native implementations of LangChain and LangGraph in `lc_core.py` and `lg_graph.py`. Make sure you're using the corrected import statements.

### File Not Found Errors
Ensure that the input and rules file paths are correct and the files exist.

## Development

### Code Structure
- `llm_router.py`: Unified interface for LLM providers
- `lc_core.py`: Native LangChain implementation
- `lg_graph.py`: Native LangGraph implementation
- `arithmetic_engine.py`: Deterministic financial calculations
- `mock_db.py`: Simulated database for lookups
- `agents_v2.py`: AI agent implementations
- `orchestrator_v2.py`: Sequential orchestrator
- `langgraph_orchestrator.py`: LangGraph-based orchestrator

### Adding New Providers
To add support for new LLM providers:
1. Extend the LLMRouter in `llm_router.py`
2. Add a new provider class in `lc_core.py`
3. Update the factory function `create_llm()`

### Testing
The system includes built-in validation:
- RuntimeTestValidatorAgent validates Excel output
- TestGenerationAgent creates and runs test cases
- DriftDetectionAgent identifies systematic errors

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.