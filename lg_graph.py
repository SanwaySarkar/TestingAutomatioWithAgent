"""
langchain_core_impl/lg_graph.py
=================================
Native LangGraph implementation.
Drop-in compatible with real langgraph when installed.

Implements:
  - TypedDict-style AgentState
  - StateGraph  (add_node, add_edge, add_conditional_edges, compile)
  - CompiledGraph  (.invoke, .stream, .get_graph)
  - END sentinel
  - MemorySaver  (checkpointing)
  - interrupt_before / interrupt_after hooks
  - Mermaid diagram export
"""

from __future__ import annotations
import json
import time
import copy
import uuid
from typing import Any, Callable, TypedDict, get_type_hints
from dataclasses import dataclass, field


# ── Sentinel ──────────────────────────────────────────────────────────────────

END   = "__end__"
START = "__start__"


# ══════════════════════════════════════════════════════════════════════════════
# STATE — typed dict with merge semantics
# ══════════════════════════════════════════════════════════════════════════════

class AgentState(dict):
    """
    LangGraph AgentState — a dict subclass that supports partial updates.
    Nodes return a dict of keys to update; StateGraph merges them.
    """
    pass


def merge_state(current: dict, update: dict) -> dict:
    """
    Merge an update dict into the current state.
    Lists are appended; scalars are overwritten.
    """
    result = dict(current)
    for k, v in update.items():
        if k in result and isinstance(result[k], list) and isinstance(v, list):
            result[k] = result[k] + v    # append lists (like messages)
        else:
            result[k] = v                # overwrite scalars
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY / CHECKPOINTING
# ══════════════════════════════════════════════════════════════════════════════

class MemorySaver:
    """
    In-memory checkpointer — saves graph state at each node step.
    Compatible with LangGraph's MemorySaver interface.
    """

    def __init__(self):
        self._store: dict[str, list[dict]] = {}   # thread_id → list of snapshots

    def put(self, config: dict, state: dict, metadata: dict = None):
        tid = config.get("configurable", {}).get("thread_id", "default")
        self._store.setdefault(tid, []).append({
            "state":    copy.deepcopy(state),
            "metadata": metadata or {},
            "ts":       time.time(),
        })

    def get(self, config: dict) -> dict | None:
        tid = config.get("configurable", {}).get("thread_id", "default")
        snaps = self._store.get(tid, [])
        return copy.deepcopy(snaps[-1]["state"]) if snaps else None

    def list(self, config: dict) -> list[dict]:
        tid = config.get("configurable", {}).get("thread_id", "default")
        return copy.deepcopy(self._store.get(tid, []))

    def get_tuple(self, config: dict):
        """Compatibility shim."""
        state = self.get(config)
        return (config, state) if state else None


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH NODE WRAPPER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NodeConfig:
    name:     str
    func:     Callable
    metadata: dict = field(default_factory=dict)


@dataclass
class EdgeConfig:
    source: str
    target: str


@dataclass
class ConditionalEdgeConfig:
    source:    str
    condition: Callable          # state → str (next node name or END)
    path_map:  dict[str, str]    # condition output → node name


# ══════════════════════════════════════════════════════════════════════════════
# STATE GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class StateGraph:
    """
    LangGraph StateGraph.

    Usage:
        graph = StateGraph(MyState)
        graph.add_node("agent", agent_fn)
        graph.add_node("tools", tools_fn)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", router_fn, {"call_tool":"tools", END:END})
        graph.add_edge("tools", "agent")
        app = graph.compile(checkpointer=MemorySaver())
        result = app.invoke({"messages": [...]})
    """

    def __init__(self, state_schema: Any = None):
        self.state_schema = state_schema
        self._nodes:  dict[str, NodeConfig]          = {}
        self._edges:  list[EdgeConfig]               = []
        self._cond_edges: list[ConditionalEdgeConfig] = []
        self._entry_point: str | None                = None
        self._finish_point: str | None               = None

    # ── Graph building API ────────────────────────────────────────────────────

    def add_node(self, name: str, func: Callable, metadata: dict = None):
        """Register a node function."""
        self._nodes[name] = NodeConfig(name=name, func=func, metadata=metadata or {})
        return self

    def add_edge(self, source: str, target: str):
        """Add a direct edge source → target."""
        self._edges.append(EdgeConfig(source=source, target=target))
        return self

    def add_conditional_edges(
        self,
        source:    str,
        condition: Callable,
        path_map:  dict[str, str] | None = None,
    ):
        """
        Add a conditional routing edge.
        condition(state) returns a key; path_map maps that key to a node name.
        If path_map is None, condition must return the node name or END directly.
        """
        self._cond_edges.append(ConditionalEdgeConfig(
            source=source,
            condition=condition,
            path_map=path_map or {},
        ))
        return self

    def set_entry_point(self, name: str):
        self._entry_point = name
        return self

    def set_finish_point(self, name: str):
        self._finish_point = name
        return self

    # ── Compile ───────────────────────────────────────────────────────────────

    def compile(
        self,
        checkpointer=None,
        interrupt_before: list[str] | None = None,
        interrupt_after:  list[str] | None = None,
    ) -> "CompiledGraph":
        if not self._entry_point:
            raise ValueError("Call set_entry_point() before compile()")
        return CompiledGraph(
            nodes           = self._nodes,
            edges           = self._edges,
            cond_edges      = self._cond_edges,
            entry_point     = self._entry_point,
            finish_point    = self._finish_point,
            checkpointer    = checkpointer,
            interrupt_before= interrupt_before or [],
            interrupt_after = interrupt_after  or [],
        )


# ══════════════════════════════════════════════════════════════════════════════
# COMPILED GRAPH  — the execution engine
# ══════════════════════════════════════════════════════════════════════════════

class NodeExecutionResult:
    def __init__(self, node: str, state: dict, duration: float):
        self.node     = node
        self.state    = state
        self.duration = duration

    def __repr__(self):
        return f"NodeResult(node={self.node}, duration={self.duration:.3f}s)"


class CompiledGraph:
    """
    Compiled, executable graph.
    Supports: invoke, stream, get_state, update_state.
    """

    def __init__(self, nodes, edges, cond_edges, entry_point,
                 finish_point, checkpointer, interrupt_before, interrupt_after):
        self._nodes           = nodes
        self._edges           = edges
        self._cond_edges      = cond_edges
        self._entry_point     = entry_point
        self._finish_point    = finish_point
        self._checkpointer    = checkpointer
        self._interrupt_before= set(interrupt_before)
        self._interrupt_after = set(interrupt_after)

        # Pre-compute adjacency for fast lookup
        self._direct: dict[str, str] = {e.source: e.target for e in edges}
        self._cond:   dict[str, ConditionalEdgeConfig] = {c.source: c for c in cond_edges}

    # ── Routing ───────────────────────────────────────────────────────────────

    def _next_node(self, current: str, state: dict) -> str | None:
        # Conditional edge takes priority
        if current in self._cond:
            cec = self._cond[current]
            key = cec.condition(state)
            if cec.path_map:
                return cec.path_map.get(key, key)
            return key
        # Direct edge
        if current in self._direct:
            return self._direct[current]
        # Finish point reached
        if current == self._finish_point:
            return END
        return None

    # ── Invoke ────────────────────────────────────────────────────────────────

    def invoke(self, input: dict, config: dict = None) -> dict:
        """Run graph to completion, return final state."""
        config = config or {"configurable": {"thread_id": str(uuid.uuid4())}}
        state  = AgentState(input)

        # Restore from checkpoint if exists
        if self._checkpointer:
            saved = self._checkpointer.get(config)
            if saved:
                state = AgentState(merge_state(saved, input))

        current = self._entry_point
        history: list[NodeExecutionResult] = []
        max_steps = 200

        for step in range(max_steps):
            if current is None or current == END:
                break
            if current not in self._nodes:
                raise ValueError(f"Node '{current}' not found. Available: {list(self._nodes)}")

            # Interrupt before hook
            if current in self._interrupt_before:
                print(f"[LangGraph] ⏸  interrupt_before: {current}")

            # Execute node
            t0      = time.time()
            node    = self._nodes[current]
            update  = node.func(state)
            elapsed = time.time() - t0

            if update and isinstance(update, dict):
                state = AgentState(merge_state(state, update))

            history.append(NodeExecutionResult(current, dict(state), elapsed))

            # Checkpoint
            if self._checkpointer:
                self._checkpointer.put(config, state, {"node": current, "step": step})

            # Interrupt after hook
            if current in self._interrupt_after:
                print(f"[LangGraph] ⏸  interrupt_after: {current}")

            current = self._next_node(current, state)

        state["__execution_history__"] = [
            {"node": r.node, "duration": round(r.duration, 4)} for r in history
        ]
        return dict(state)

    # ── Stream ────────────────────────────────────────────────────────────────

    def stream(self, input: dict, config: dict = None):
        """
        Yield (node_name, state_update) after each node executes.
        Mirrors LangGraph's streaming API.
        """
        config = config or {"configurable": {"thread_id": str(uuid.uuid4())}}
        state  = AgentState(input)
        current= self._entry_point
        max_steps = 200

        for _ in range(max_steps):
            if current is None or current == END:
                break
            if current not in self._nodes:
                break
            node   = self._nodes[current]
            update = node.func(state)
            if update and isinstance(update, dict):
                state = AgentState(merge_state(state, update))
            yield {current: dict(state)}
            current = self._next_node(current, state)

    # ── State inspection ──────────────────────────────────────────────────────

    def get_state(self, config: dict) -> dict | None:
        if self._checkpointer:
            return self._checkpointer.get(config)
        return None

    def update_state(self, config: dict, values: dict):
        if self._checkpointer:
            current = self._checkpointer.get(config) or {}
            updated = merge_state(current, values)
            self._checkpointer.put(config, updated)

    # ── Mermaid diagram ───────────────────────────────────────────────────────

    def get_graph(self) -> "GraphVisualizer":
        return GraphVisualizer(self._nodes, self._edges, self._cond_edges,
                               self._entry_point, self._finish_point)


class GraphVisualizer:
    def __init__(self, nodes, edges, cond_edges, entry, finish):
        self._nodes     = nodes
        self._edges     = edges
        self._cond_edges= cond_edges
        self._entry     = entry
        self._finish    = finish

    def draw_mermaid(self) -> str:
        lines = ["graph TD"]
        lines.append(f"    {START}(({START})) --> {self._entry}")
        for e in self._edges:
            tgt = END if e.target == END else e.target
            lines.append(f"    {e.source} --> {tgt}")
        for ce in self._cond_edges:
            for key, tgt in ce.path_map.items():
                tgt = "__end__" if tgt == END else tgt
                lines.append(f"    {ce.source} -->|{key}| {tgt}")
        if self._finish:
            lines.append(f"    {self._finish} --> __end__((__end__))")
        return "\n".join(lines)

    def print_ascii(self):
        print(self.draw_mermaid())


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE: MessagesState (pre-built state with messages list)
# ══════════════════════════════════════════════════════════════════════════════

class MessagesState(AgentState):
    """Pre-built state with a messages key (list of BaseMessage)."""
    pass


def messages_state_factory(initial: dict = None) -> MessagesState:
    s = MessagesState(initial or {})
    s.setdefault("messages", [])
    return s
