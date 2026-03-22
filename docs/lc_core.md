# LangChain Core Implementation Documentation

## Overview

The `lc_core.py` file provides a native implementation of LangChain core primitives, offering drop-in compatibility with the real langchain-core library when installed. This implementation enables the project to run without external LangChain dependencies.

## Implemented Components

### Messages
- `BaseMessage`: Base class for all message types
- `HumanMessage`: Represents user input
- `SystemMessage`: Represents system instructions
- `AIMessage`: Represents AI responses
- `ToolMessage`: Represents tool responses

### Prompt Templates
- `PromptTemplate`: Simple string prompt template
- `ChatPromptTemplate`: Chat prompt with system and human messages

### Output Parsers
- `StrOutputParser`: Parses LLM output as plain string
- `JsonOutputParser`: Parses LLM output as JSON, stripping markdown fences
- `CommaSeparatedListOutputParser`: Parses comma-separated lists

### Base Chat Model
- `BaseChatModel`: Abstract base class for chat models
- `ChatAnthropic`: Claude wrapper
- `ChatGoogleGenerativeAI`: Gemini wrapper
- `ChatOllama`: Ollama wrapper

### Runnables (LCEL - LangChain Expression Language)
- `Runnable`: Base runnable interface
- `LCChain`: Composable chain supporting pipe operator
- `RunnableLambda`: Wraps functions as runnables
- `RunnablePassthrough`: Passes input through unchanged
- `RunnableAssign`: Merges computed keys into input dict
- `RunnableParallel`: Runs multiple runnables in parallel

### Tools
- `Tool`: Basic tool implementation
- `StructuredTool`: Tool with typed arguments schema

### Memory
- `ConversationBufferMemory`: Simple conversation history buffer

## Factory Functions

### `create_llm()`
Factory function that creates the appropriate chat model based on provider string:
- "claude": Creates `ChatAnthropic`
- "gemini": Creates `ChatGoogleGenerativeAI`
- "ollama": Creates `ChatOllama`

### `create_chain()`
Convenience function to build prompt | llm | parser chains.

## Key Features

### Pipe Operator Support
All components support the `|` operator for chaining, mimicking LangChain's LCEL:
```python
chain = prompt | llm | parser
```

### Provider Compatibility
Each provider wrapper handles the specific API requirements:
- Claude: Uses anthropic package if available
- Gemini: Uses REST API with API key
- Ollama: Uses REST API with local server

### JSON Parsing
Robust JSON extraction that removes markdown fences and finds the first valid JSON object or array in LLM responses.

### Error Handling
Graceful degradation when providers are unavailable, with informative error messages.

## Usage Examples

```python
# Create an LLM
llm = create_llm("gemini", model="gemini-2.0-flash")

# Create a prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{question}")
])

# Create a chain
chain = prompt | llm | StrOutputParser()

# Invoke the chain
response = chain.invoke({"question": "What is the capital of France?"})
```

## Implementation Details

The implementation focuses on compatibility with LangChain's interface while being lightweight and self-contained. It avoids external dependencies where possible and provides sensible fallbacks for missing functionality.