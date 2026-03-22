# """
# llm_router.py
# =============
# Unified LLM interface supporting:
#   - Claude   (Anthropic)  — provider="claude"
#   - Gemini   (Google)     — provider="gemini"
#   - Ollama   (local)      — provider="ollama"

# Usage:
#     router = LLMRouter(provider="gemini", model="gemini-2.0-flash")
#     text   = router.call(system="...", user="...")
#     data   = router.call_json(system="...", user="...")

# All providers normalise to the same interface.
# """

# from __future__ import annotations
# import json
# import re
# import os
# import urllib.request
# import urllib.error
# from typing import Any


# # ── Provider implementations ──────────────────────────────────────────────────

# class _ClaudeProvider:
#     NAME = "claude"

#     def __init__(self, model: str = "claude-sonnet-4-20250514"):
#         self.model = model
#         try:
#             import anthropic
#             self._client = anthropic.Anthropic()
#             self.available = True
#         except Exception as e:
#             self._client = None
#             self.available = False
#             print(f"[LLMRouter] Claude unavailable: {e}")

#     def call(self, system: str, user: str, max_tokens: int = 3000) -> str:
#         if not self.available:
#             return ""
#         resp = self._client.messages.create(
#             model=self.model,
#             max_tokens=max_tokens,
#             system=system,
#             messages=[{"role": "user", "content": user}],
#         )
#         return resp.content[0].text.strip()


# class _GeminiProvider:
#     NAME = "gemini"

#     def __init__(self, model: str = "gemini-2.5-flash"):
#         self.model = model
#         print(f"[LLMRouter] Gemini: using model {self.model}")
#         self.api_key = os.environ.get("GEMINI_API_KEY", "")
#         self.available = bool(self.api_key)
#         if not self.available:
#             print("[LLMRouter] Gemini: GEMINI_API_KEY not set — provider unavailable")

#     def call(self, system: str, user: str, max_tokens: int = 3000) -> str:
#         if not self.available:
#             return ""
#         url = (
#             f"https://generativelanguage.googleapis.com/v1beta/models/"
#             f"{self.model}:generateContent?key={self.api_key}"
#         )
#         payload = json.dumps({
#             "contents": [
#                 {"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}
#             ],
#             "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
#         }).encode()

#         req = urllib.request.Request(
#             url, data=payload,
#             headers={"Content-Type": "application/json"},
#             method="POST",
#         )
#         try:
#             with urllib.request.urlopen(req, timeout=60) as resp:
#                 data = json.loads(resp.read())
#             return data["candidates"][0]["content"]["parts"][0]["text"].strip()
#         except Exception as e:
#             print(f"[LLMRouter] Gemini call failed: {e}")
#             return ""


# class _OllamaProvider:
#     NAME = "ollama"

#     def __init__(self, model: str = "qwen3-coder:30b", host: str = "http://localhost:11434"):
#         self.model = model
#         self.host  = host.rstrip("/")
#         self.available = self._ping()

#     def _ping(self) -> bool:
#         try:
#             req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
#             with urllib.request.urlopen(req, timeout=5):
#                 return True
#         except Exception:
#             print(f"[LLMRouter] Ollama: cannot reach {self.host} — provider unavailable")
#             return False

#     def call(self, system: str, user: str, max_tokens: int = 3000) -> str:
#         if not self.available:
#             return ""
#         payload = json.dumps({
#             "model": self.model,
#             "prompt": f"<system>\n{system}\n</system>\n\n{user}",
#             "stream": False,
#             "options": {"num_predict": max_tokens, "temperature": 0.1},
#         }).encode()
#         req = urllib.request.Request(
#             f"{self.host}/api/generate",
#             data=payload,
#             headers={"Content-Type": "application/json"},
#             method="POST",
#         )
#         try:
#             with urllib.request.urlopen(req, timeout=120) as resp:
#                 data = json.loads(resp.read())
#             return data.get("response", "").strip()
#         except Exception as e:
#             print(f"[LLMRouter] Ollama call failed: {e}")
#             return ""


# # ── Router ────────────────────────────────────────────────────────────────────

# PROVIDER_MAP = {
#     "claude": _ClaudeProvider,
#     "gemini": _GeminiProvider,
#     "ollama": _OllamaProvider,
# }


# class LLMRouter:
#     """
#     Single interface for all LLM providers.
#     Falls back through a chain if the primary provider is unavailable.

#     fallback_chain: list of (provider, model) pairs tried in order.
#     """

#     def __init__(
#         self,
#         provider: str = "claude",
#         model:    str | None = None,
#         ollama_host: str = "http://localhost:11434",
#         fallback_chain: list[tuple[str, str]] | None = None,
#     ):
#         self.primary_provider = provider.lower()
#         self.fallback_chain   = fallback_chain or []

#         # Default models per provider
#         defaults = {
#             "claude": "claude-sonnet-4-20250514",
#             "gemini": "gemini-2.5-flash",
#             "ollama": "qwen3-coder:30b",
#         }
#         self.primary_model = model or defaults.get(self.primary_provider, "")
#         self.ollama_host   = ollama_host

#         self._providers: list[Any] = []
#         self._init_providers()

#     def _make_provider(self, name: str, model: str):
#         cls = PROVIDER_MAP.get(name.lower())
#         if not cls:
#             print(f"[LLMRouter] Unknown provider '{name}'")
#             return None
#         if name.lower() == "ollama":
#             return cls(model=model, host=self.ollama_host)
#         return cls(model=model)

#     def _init_providers(self):
#         primary = self._make_provider(self.primary_provider, self.primary_model)
#         if primary:
#             self._providers.append(primary)

#         for fb_provider, fb_model in self.fallback_chain:
#             p = self._make_provider(fb_provider, fb_model)
#             if p:
#                 self._providers.append(p)

#     @property
#     def active_provider(self) -> str:
#         for p in self._providers:
#             if getattr(p, "available", False):
#                 return p.NAME
#         return "none"

#     def call(self, system: str, user: str, max_tokens: int = 3000) -> str:
#         """Call LLM with fallback. Returns plain text."""
#         for p in self._providers:
#             if not getattr(p, "available", False):
#                 continue
#             result = p.call(system, user, max_tokens)
#             if result:
#                 return result
#         return ""

#     def call_json(self, system: str, user: str, max_tokens: int = 3000) -> dict | list:
#         """Call LLM, extract and parse JSON from response."""
#         raw = self.call(
#             system + "\n\nRespond ONLY with valid JSON. No markdown fences, no prose before or after.",
#             user,
#             max_tokens,
#         )
#         if not raw:
#             return {}
#         # Strip markdown fences if model added them anyway
#         raw = re.sub(r"```json\s*|```\s*", "", raw).strip()
#         # Extract first JSON object/array
#         match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
#         if match:
#             raw = match.group(1)
#         try:
#             return json.loads(raw)
#         except Exception:
#             return {}

#     def describe(self) -> str:
#         parts = []
#         for p in self._providers:
#             avail = "✅" if getattr(p, "available", False) else "❌"
#             parts.append(f"{avail} {p.NAME}({getattr(p,'model','')})")
#         return " | ".join(parts) or "no providers"
