"""Model Provider Protocol — SPI for LLM model providers.

Every model plugin (OpenAI, Anthropic, Ollama, vLLM) implements this protocol.
The AI Gateway routes requests to the appropriate provider through this interface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ModelRequest:
    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[dict[str, Any]] = field(default_factory=list)
    stream: bool = False


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: dict[str, int] | None = None


@dataclass
class ModelChunk:
    content: str
    done: bool = False


@dataclass
class ModelHealth:
    healthy: bool
    model: str
    latency_ms: float = 0.0
    error: str | None = None


class ModelProviderProtocol(Protocol):
    """Protocol that every model plugin must implement."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...

    async def generate_stream(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        ...

    async def health(self) -> ModelHealth:
        ...
