"""Local model adapter (self-contained, no RuntimeManager dependency)."""

import uuid
from datetime import datetime

from core.contracts.adapter import StreamChunk


class LocalModelAdapter:
    """Local LLM adapter (self-contained, no RuntimeManager dependency)."""

    def __init__(self, model_name: str = "llama-local") -> None:
        self._model_name = model_name
        self._metadata = {
            "adapter_id": "local",
            "name": "Local LLM",
            "version": "1.0",
            "capabilities": ("model.text.generate", "model.code.generate"),
            "provider": "local",
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    async def execute(self, request: dict) -> dict:
        prompt = request.get("payload", {}).get("prompt", "")
        request_id = uuid.uuid4().hex[:12]
        # Mock local execution
        result = {
            "text": f"Local response to: {prompt[:50]}...",
            "request_id": uuid.uuid4().hex[:12],
            "finish_reason": "stop",
            "execution": {"runtime": "local", "device": "cpu", "memory_mb": 0},
            "billing": {"input_units": len(prompt), "output_units": 50},
            "trace": {"request_id": uuid.uuid4().hex[:12]},
        }
        return {
            "success": True,
            "result": result,
            "usage": {
                "capability": "chat.generate",
                "adapter_id": "local",
                "timestamp": datetime.now().isoformat(),
                "input_units": len(prompt),
                "output_units": 50,
                "cost": None,
                "provider_id": "local",
            },
        }

    async def execute_stream(self, request: dict):
        prompt = request.get("payload", {}).get("prompt", "")
        # Simple streaming mock
        text = f"Local response to: {prompt[:50]}..."
        for i in range(0, len(text), 10):
            yield StreamChunk(content=text[i:i+10])
        yield StreamChunk(content=None, finish_reason="stop")

    async def health_check(self) -> dict:
        return {"healthy": True, "provider": "local", "model": self._model_name}

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        caps = frozenset(self._metadata.get("capabilities", ()))
        return required_capabilities.issubset(caps)

    def get_capabilities(self) -> tuple[str, ...]:
        return ("model.text.generate", "model.code.generate")
