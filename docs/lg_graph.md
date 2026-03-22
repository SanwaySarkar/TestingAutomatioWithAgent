# LangGraph Implementation Documentation

## Overview

The `lg_graph.py` file provides a native implementation of LangGraph primitives, offering drop-in compatibility with the real langgraph library when installed. This implementation enables complex workflow orchestration without external dependencies.

## Implemented Components

### Core Primitives
- `END`: Sentinel value indicating graph termination
- `START`: Sentinel value indicating graph entry point
- `AgentState`: Typed dictionary with merge semantics for graph state
- `MemorySaver`: In-memory checkpointing for state persistence

### Graph Building
- `StateGraph`: Main class for defining stateful graphs
- `NodeConfig`: Configuration for graph nodes
- `EdgeConfig`: Configuration for direct edges
- `ConditionalEdgeConfig`: Configuration for conditional routing

### Graph Execution
- `CompiledGraph`: Executable graph with invoke and stream methods
- `NodeExecutionResult`: Results from individual node executions
- `GraphVisualizer`: Mermaid diagram generation for graph visualization

## Key Features

### State Management
The `AgentState` class extends Python's dict with merge semantics:
- Scalar values are overwritten
- Lists are appended (useful for message histories)
- Partial state updates are automatically merged

### Checkpointing
The `MemorySaver` class provides in-memory state persistence:
- Saves graph state after each node execution
- Restores state from checkpoints when resuming
- Maintains execution history for debugging

### Conditional Routing
Supports complex routing logic:
- Direct edges: One node always leads to another
- Conditional edges: Routing determined by state-based conditions
- Path mapping: Condition outputs mapped to node names

### Visualization
Built-in Mermaid diagram generation for visualizing graph structure.

## Usage Examples

### Basic Graph
```python
from lg_graph import StateGraph, END

# Define state schema
class MyState(AgentState):
    pass

# Create graph
graph = StateGraph(MyState)

# Add nodes
graph.add_node("agent1", agent1_func)
graph.add_node("agent2", agent2_func)

# Define flow
graph.set_entry_point("agent1")
graph.add_edge("agent1", "agent2")
graph.add_edge("agent2", END)

# Compile and run
app = graph.compile()
result = app.invoke({"initial": "state"})
```

### Conditional Edges
```python
def route_logic(state):
    if state.get("needs_review"):
        return "review"
    return "continue"

graph.add_conditional_edges(
    "agent1",
    route_logic,
    {
        "review": "review_agent",
        "continue": "next_agent"
    }
)
```

### Streaming
```python
# Stream intermediate results
for event in app.stream({"input": "data"}):
    node_name = list(event.keys())[0]
    print(f"Completed: {node_name}")
```

## Graph Building API

### Methods

#### `add_node(name, func, metadata=None)`
Registers a node function with the graph.

#### `add_edge(source, target)`
Adds a direct edge from source to target node.

#### `add_conditional_edges(source, condition, path_map=None)`
Adds conditional routing based on state evaluation.

#### `set_entry_point(name)`
Sets the starting node for the graph.

#### `set_finish_point(name)`
Sets a node that leads directly to END.

#### `compile(checkpointer=None, interrupt_before=None, interrupt_after=None)`
Compiles the graph into an executable form.

## Execution Model

### Invoke Method
Runs the graph to completion and returns the final state:
- Restores from checkpoint if available
- Executes nodes in sequence based on edges
- Handles conditional routing
- Supports interruption points for manual review

### Stream Method
Yields intermediate results after each node execution:
- Enables real-time monitoring of graph progress
- Useful for long-running workflows
- Provides visibility into intermediate states

## State Merge Logic

The `merge_state` function implements intelligent merging:
- Lists are concatenated (preserving history)
- Scalars are replaced (updating current values)
- Nested dictionaries are recursively merged
- Missing keys are initialized appropriately

## MemorySaver Checkpointer

Provides in-memory state persistence:
- Stores snapshots of graph state after each step
- Retrieves previous states for resumption
- Maintains metadata about each checkpoint
- Thread-safe storage using configurable thread IDs

## Graph Visualization

The `GraphVisualizer` generates Mermaid diagrams:
- Shows all nodes and their connections
- Displays conditional routing paths
- Indicates entry and exit points
- Compatible with Mermaid live editors

## Implementation Details

The implementation prioritizes compatibility with LangGraph's interface while maintaining simplicity and performance. It uses standard Python data structures and avoids external dependencies where possible.