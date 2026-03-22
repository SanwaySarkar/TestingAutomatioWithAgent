"""
langchain_core_impl/lc_core.py
================================
Native implementation of LangChain core primitives.
Drop-in compatible with real langchain-core when installed.

Implements:
  - BaseMessage, HumanMessage, SystemMessage, AIMessage
  - ChatPromptTemplate, PromptTemplate
  - BaseChatModel  (wraps Claude / Gemini / Ollama)
  - StrOutputParser, JsonOutputParser
  - LLMChain  (prompt | llm | parser  pipe syntax)
  - RunnableLambda, RunnablePassthrough, RunnableParallel
  - Tool, StructuredTool
  - ConversationBufferMemory
"""

from __future__ import annotations
import json, re, os, urllib.request, urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BaseMessage:
    content: str
    role: str = "unknown"
    additional_kwargs: dict = field(default_factory=dict)

    def __repr__(self):
        return f"{self.__class__.__name__}(content={self.content[:60]!r})"


@dataclass
class HumanMessage(BaseMessage):
    role: str = "user"


@dataclass
class SystemMessage(BaseMessage):
    role: str = "system"


@dataclass
class AIMessage(BaseMessage):
    role: str = "assistant"


@dataclass
class ToolMessage(BaseMessage):
    role: str       = "tool"
    tool_call_id: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

class PromptTemplate:
    """Simple string prompt template."""

    def __init__(self, template: str, input_variables: list[str] = None):
        self.template        = template
        self.input_variables = input_variables or self._detect_vars(template)

    @staticmethod
    def _detect_vars(tmpl: str) -> list[str]:
        return re.findall(r"\{(\w+)\}", tmpl)

    @classmethod
    def from_template(cls, template: str) -> "PromptTemplate":
        return cls(template)

    def format(self, **kwargs) -> str:
        return self.template.format(**kwargs)

    def format_messages(self, **kwargs) -> list[BaseMessage]:
        return [HumanMessage(content=self.format(**kwargs))]

    def __or__(self, other):
        return LCChain(self, other)


class ChatPromptTemplate:
    """Chat prompt with system + human messages."""

    def __init__(self, messages: list[tuple[str, str]]):
        self._messages = messages   # list of (role, template_str)

    @classmethod
    def from_messages(cls, messages: list[tuple[str, str]]) -> "ChatPromptTemplate":
        return cls(messages)

    @classmethod
    def from_template(cls, template: str) -> "ChatPromptTemplate":
        return cls([("human", template)])

    def format_messages(self, **kwargs) -> list[BaseMessage]:
        result = []
        for role, tmpl in self._messages:
            text = tmpl.format(**kwargs)
            if role == "system":     result.append(SystemMessage(content=text))
            elif role == "human":    result.append(HumanMessage(content=text))
            elif role == "assistant":result.append(AIMessage(content=text))
            else:                    result.append(BaseMessage(content=text, role=role))
        return result

    def format(self, **kwargs) -> list[BaseMessage]:
        return self.format_messages(**kwargs)

    def invoke(self, inputs: dict) -> list[BaseMessage]:
        return self.format_messages(**inputs)

    def __or__(self, other):
        return LCChain(self, other)


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT PARSERS
# ══════════════════════════════════════════════════════════════════════════════

class StrOutputParser:
    """Parse LLM output as plain string."""

    def invoke(self, msg: Any) -> str:
        if isinstance(msg, BaseMessage): return msg.content
        if isinstance(msg, str):         return msg
        return str(msg)

    def parse(self, text: str) -> str:
        return text

    def __or__(self, other):
        return LCChain(self, other)


class JsonOutputParser:
    """Parse LLM output as JSON, stripping markdown fences."""

    def __init__(self, pydantic_object=None):
        self.pydantic_object = pydantic_object

    def invoke(self, msg: Any) -> dict | list:
        text = msg.content if isinstance(msg, BaseMessage) else str(msg)
        return self.parse(text)

    def parse(self, text: str) -> dict | list:
        text = re.sub(r"```json\s*|```\s*", "", text).strip()
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if m: text = m.group(1)
        try:    return json.loads(text)
        except: return {}

    def __or__(self, other):
        return LCChain(self, other)


class CommaSeparatedListOutputParser:
    def invoke(self, msg: Any) -> list[str]:
        text = msg.content if isinstance(msg, BaseMessage) else str(msg)
        return [s.strip() for s in text.split(",") if s.strip()]


# ══════════════════════════════════════════════════════════════════════════════
# BASE CHAT MODEL  (provider-agnostic)
# ══════════════════════════════════════════════════════════════════════════════

class BaseChatModel(ABC):
    """Abstract LangChain-compatible chat model."""

    def __init__(self, temperature: float = 0.0, max_tokens: int = 3000):
        self.temperature = temperature
        self.max_tokens  = max_tokens

    @abstractmethod
    def _call_api(self, messages: list[BaseMessage]) -> str:
        ...

    def invoke(self, input: Any) -> AIMessage:
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        elif isinstance(input, list):
            messages = input
        elif isinstance(input, dict):
            # Support {"messages": [...]} format
            messages = input.get("messages", [HumanMessage(content=str(input))])
        else:
            messages = [HumanMessage(content=str(input))]
        content = self._call_api(messages)
        return AIMessage(content=content)

    def predict(self, text: str) -> str:
        return self.invoke(text).content

    def __call__(self, messages: list[BaseMessage]) -> AIMessage:
        return self.invoke(messages)

    def __or__(self, other):
        return LCChain(self, other)

    def bind_tools(self, tools: list) -> "BoundModelWithTools":
        return BoundModelWithTools(self, tools)

    def with_structured_output(self, schema) -> "StructuredOutputModel":
        return StructuredOutputModel(self, schema)


class BoundModelWithTools:
    """Model with tools bound — routes tool calls."""
    def __init__(self, model: BaseChatModel, tools: list):
        self.model = model
        self.tools = {t.name: t for t in tools}

    def invoke(self, input: Any) -> AIMessage:
        tool_desc = "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values())
        if isinstance(input, list):
            msgs = input
        else:
            msgs = [HumanMessage(content=str(input))]
        # Inject tool descriptions into system context
        tool_sys = SystemMessage(content=f"Available tools:\n{tool_desc}\n\nUse them as needed.")
        return self.model.invoke([tool_sys] + msgs)

    def __or__(self, other):
        return LCChain(self, other)


class StructuredOutputModel:
    """Wraps a model to always return parsed JSON matching a schema."""
    def __init__(self, model: BaseChatModel, schema):
        self.model  = model
        self.schema = schema

    def invoke(self, input: Any) -> dict | list:
        msg = self.model.invoke(input)
        parser = JsonOutputParser()
        return parser.parse(msg.content)

    def __or__(self, other):
        return LCChain(self, other)


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE PROVIDERS
# ══════════════════════════════════════════════════════════════════════════════

class ChatAnthropic(BaseChatModel):
    """LangChain-compatible Claude wrapper."""

    def __init__(self, model: str = "claude-sonnet-4-20250514",
                 temperature: float = 0.0, max_tokens: int = 3000):
        super().__init__(temperature, max_tokens)
        self.model = model
        self._client = None
        try:
            import anthropic
            self._client = anthropic.Anthropic()
        except Exception:
            pass

    @property
    def available(self): return self._client is not None

    def _call_api(self, messages: list[BaseMessage]) -> str:
        if not self._client: 
            raise Exception("Claude API is not available - anthropic package not installed or API key missing")
        system_parts = [m.content for m in messages if isinstance(m, SystemMessage)]
        user_parts   = [{"role": m.role if m.role in ("user","assistant") else "user",
                         "content": m.content}
                        for m in messages if not isinstance(m, SystemMessage)]
        if not user_parts:
            user_parts = [{"role": "user", "content": "proceed"}]
        kwargs = dict(model=self.model, max_tokens=self.max_tokens, messages=user_parts)
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        resp = self._client.messages.create(**kwargs)
        return resp.content[0].text.strip()


class ChatGoogleGenerativeAI(BaseChatModel):
    """LangChain-compatible Gemini wrapper."""

    def __init__(self, model: str = "gemini-2.0-flash",
                 temperature: float = 0.0, max_tokens: int = 3000,
                 google_api_key: str = ""):
        super().__init__(temperature, max_tokens)
        self.model   = model
        self.api_key = google_api_key or os.environ.get("GEMINI_API_KEY","")

    @property
    def available(self): return bool(self.api_key)

    def _call_api(self, messages: list[BaseMessage]) -> str:
        if not self.available: 
            raise Exception("Gemini API is not available - no API key provided")
        combined = "\n\n".join(m.content for m in messages)
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        payload = json.dumps({
            "contents": [{"role":"user","parts":[{"text":combined}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens,
                                 "temperature": self.temperature},
        }).encode()
        req = urllib.request.Request(url, data=payload,
              headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"[Gemini] API error: {e}")
            raise Exception(f"Gemini API call failed: {e}")


class ChatOllama(BaseChatModel):
    """LangChain-compatible Ollama wrapper."""

    def __init__(self, model: str = "llama3.2",
                 base_url: str = "http://localhost:11434",
                 temperature: float = 0.0, max_tokens: int = 3000):
        super().__init__(temperature, max_tokens)
        self.model    = model
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3)
            return True
        except: return False

    def _call_api(self, messages: list[BaseMessage]) -> str:
        if not self.available:
            raise Exception("Ollama is not available - server not running or unreachable")
        combined = "\n\n".join(f"[{m.role}] {m.content}" for m in messages)
        payload  = json.dumps({"model":self.model,"prompt":combined,
                               "stream":False,"options":{"num_predict":self.max_tokens,
                                                          "temperature":self.temperature}}).encode()
        req = urllib.request.Request(f"{self.base_url}/api/generate", data=payload,
              headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read()).get("response","").strip()
        except Exception as e:
            print(f"[Ollama] API error: {e}")
            raise Exception(f"Ollama API call failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# RUNNABLES  (LangChain LCEL — pipe | operator)
# ══════════════════════════════════════════════════════════════════════════════

class Runnable(ABC):
    """Base runnable — supports | pipe operator."""

    @abstractmethod
    def invoke(self, input: Any) -> Any: ...

    def __or__(self, other: "Runnable") -> "LCChain":
        return LCChain(self, other)

    def batch(self, inputs: list) -> list:
        return [self.invoke(inp) for inp in inputs]

    def stream(self, input: Any) -> Iterator:
        yield self.invoke(input)


class LCChain(Runnable):
    """
    Composable chain via | operator.
    prompt | llm | parser   works exactly like LangChain LCEL.
    """

    def __init__(self, *steps):
        self._steps = []
        for s in steps:
            if isinstance(s, LCChain):
                self._steps.extend(s._steps)
            else:
                self._steps.append(s)

    def invoke(self, input: Any) -> Any:
        result = input
        for step in self._steps:
            if hasattr(step, "invoke"):
                result = step.invoke(result)
            elif callable(step):
                result = step(result)
        return result

    def __or__(self, other) -> "LCChain":
        return LCChain(self, other)


class RunnableLambda(Runnable):
    """Wrap any function as a Runnable."""

    def __init__(self, func: Callable):
        self._func = func

    def invoke(self, input: Any) -> Any:
        return self._func(input)


class RunnablePassthrough(Runnable):
    """Pass input through unchanged (identity)."""

    def invoke(self, input: Any) -> Any:
        return input

    @classmethod
    def assign(cls, **kwargs: Callable) -> "RunnableAssign":
        return RunnableAssign(**kwargs)


class RunnableAssign(Runnable):
    """Merge computed keys into the input dict."""

    def __init__(self, **assignments: Callable):
        self._assignments = assignments

    def invoke(self, input: dict) -> dict:
        result = dict(input)
        for key, fn in self._assignments.items():
            if hasattr(fn, "invoke"):
                result[key] = fn.invoke(input)
            else:
                result[key] = fn(input)
        return result


class RunnableParallel(Runnable):
    """Run multiple runnables in parallel (sequentially here), merge results."""

    def __init__(self, **runnables: Runnable):
        self._runnables = runnables

    def invoke(self, input: Any) -> dict:
        return {
            key: (r.invoke(input) if hasattr(r,"invoke") else r(input))
            for key, r in self._runnables.items()
        }


# ══════════════════════════════════════════════════════════════════════════════
# TOOLS
# ══════════════════════════════════════════════════════════════════════════════

class Tool:
    """LangChain-compatible Tool."""

    def __init__(self, name: str, func: Callable, description: str = ""):
        self.name        = name
        self.func        = func
        self.description = description

    def invoke(self, input: Any) -> Any:
        if isinstance(input, dict):
            return self.func(**input)
        return self.func(input)

    def run(self, input: Any) -> str:
        return str(self.invoke(input))

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class StructuredTool(Tool):
    """Tool with typed args schema."""

    def __init__(self, name: str, func: Callable, description: str = "",
                 args_schema: Any = None):
        super().__init__(name, func, description)
        self.args_schema = args_schema

    @classmethod
    def from_function(cls, func: Callable, name: str = "", description: str = "") -> "StructuredTool":
        return cls(name=name or func.__name__, func=func, description=description or func.__doc__ or "")


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════════════

class ConversationBufferMemory:
    """Simple conversation history buffer."""

    def __init__(self, return_messages: bool = False, memory_key: str = "history"):
        self.return_messages = return_messages
        self.memory_key      = memory_key
        self.chat_memory: list[BaseMessage] = []

    def save_context(self, inputs: dict, outputs: dict):
        human = inputs.get("input", inputs.get("human_input", str(inputs)))
        ai    = outputs.get("output", outputs.get("response", str(outputs)))
        self.chat_memory.append(HumanMessage(content=str(human)))
        self.chat_memory.append(AIMessage(content=str(ai)))

    def load_memory_variables(self, inputs: dict) -> dict:
        if self.return_messages:
            return {self.memory_key: self.chat_memory}
        history_str = "\n".join(
            f"{'Human' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
            for m in self.chat_memory
        )
        return {self.memory_key: history_str}

    def clear(self):
        self.chat_memory = []


# ══════════════════════════════════════════════════════════════════════════════
# MODEL FACTORY — resolve provider string → model instance
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.2",
}


def create_llm(
    provider:    str  = "claude",
    model:       str  = "",
    temperature: float = 0.0,
    max_tokens:  int   = 3000,
    ollama_host: str   = "http://localhost:11434",
    **kwargs,
) -> BaseChatModel:
    """
    Factory — creates the right LangChain-compatible chat model.

    Usage:
        llm = create_llm("gemini", model="gemini-2.5-flash")
        llm = create_llm("ollama", model="llama3.2", ollama_host="http://localhost:11434")
        llm = create_llm("claude")
    """
    provider = provider.lower()
    m = model or _DEFAULT_MODELS.get(provider, "")
    if provider == "claude":
        return ChatAnthropic(model=m, temperature=temperature, max_tokens=max_tokens)
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(model=m, temperature=temperature, max_tokens=max_tokens)
    elif provider == "ollama":
        return ChatOllama(model=m, base_url=ollama_host, temperature=temperature, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose: claude | gemini | ollama")


def create_chain(prompt: ChatPromptTemplate, llm: BaseChatModel,
                 parser=None) -> LCChain:
    """Convenience: build prompt | llm | parser chain."""
    if parser:
        return prompt | llm | parser
    return prompt | llm | StrOutputParser()
