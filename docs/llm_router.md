# LLM Router Documentation

## Overview

The `llm_router.py` file provides a unified interface for interacting with multiple Large Language Model (LLM) providers. It supports Anthropic's Claude, Google's Gemini, and locally hosted Ollama models. This router enables seamless switching between providers and implements fallback mechanisms.

## Features

- **Multi-provider Support**: Works with Claude, Gemini, and Ollama
- **Fallback Chain**: Automatically falls back to alternative providers if the primary is unavailable
- **JSON Parsing**: Built-in extraction and parsing of JSON from LLM responses
- **Consistent Interface**: All providers expose the same API methods

## Supported Providers

1. **Claude** (Anthropic) - `provider="claude"`
2. **Gemini** (Google) - `provider="gemini"`
3. **Ollama** (Local) - `provider="ollama"`

## Usage

```python
from llm_router import LLMRouter

# Basic usage
router = LLMRouter(provider="gemini", model="gemini-2.0-flash")
text = router.call(system="System prompt", user="User message")

# With fallback chain
router = LLMRouter(
    provider="claude",
    model="claude-sonnet-4-20250514",
    fallback_chain=[("gemini", "gemini-2.0-flash")]
)

# JSON response parsing
data = router.call_json(system="Respond only with JSON", user="Generate data")
```

## Provider Classes

### `_ClaudeProvider`
Wrapper for Anthropic's Claude API.

**Requirements**: `anthropic` Python package
**Default Model**: `claude-sonnet-4-20250514`

### `_GeminiProvider`
Wrapper for Google's Gemini API.

**API Key**: Requires `GEMINI_API_KEY` environment variable
**Default Model**: `gemini-2.0-flash`

### `_OllamaProvider`
Wrapper for locally hosted Ollama models.

**Host**: Default `http://localhost:11434`
**Default Model**: `qwen3-coder:30b`

## Main Class: LLMRouter

### Constructor Parameters
- `provider`: Primary provider name (default: "claude")
- `model`: Specific model name (uses provider default if None)
- `ollama_host`: Ollama server URL (default: "http://localhost:11434")
- `fallback_chain`: List of (provider, model) tuples for fallback

### Methods

#### `call(system, user, max_tokens)`
Calls the LLM with system and user prompts, returning plain text.

#### `call_json(system, user, max_tokens)`
Calls the LLM and extracts/parses JSON from the response.

#### `describe()`
Returns a string describing the available providers and their status.

#### `active_provider`
Property that returns the name of the currently active provider.

## Implementation Details

The router normalizes all providers to the same interface, handling differences in API calls transparently. It automatically strips markdown code fences from JSON responses and extracts the first valid JSON object or array.

Fallback chains are processed in order, with the router attempting each provider until one succeeds or all are exhausted.