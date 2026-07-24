"""OpenAI GPT model adapter."""

import uuid
from datetime import datetime
from typing import Any
from collections.abc import AsyncIterator

from services.ai_gateway.interfaces.adapter import StreamChunk


async def _call_openai(prompt: str, model: str, api_key: str, base_url: str) -> dict[str, Any]:
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})
        return {
            "text": text,
            "input_units": usage.get("prompt_tokens", len(prompt)),
            "output_units": usage.get("completion_tokens", len(text)),
        }


async def _stream_openai(prompt: str, model: str, api_key: str, base_url: str):
    import httpx
    import json
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip() or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    yield StreamChunk(content=None, finish_reason="stop")
                    return
                try:
                    chunk = json.loads(line)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield StreamChunk(content=content)
                except json.JSONDecodeError:
                    continue


class OpenAIAdapter:
    """OpenAI GPT model adapter."""
    
    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._metadata = {
            "adapter_id": "openai",
            "name": "OpenAI GPT",
            "version": "1.0",
            "capabilities": ("model.text.generate", "model.code.generate", "model.embed.create"),
            "provider": "openai",
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    async def execute(self, request: dict) -> dict:
        from uuid import uuid4
        prompt = request.get("payload", {}).get("prompt", "")
        request_id = uuid.uuid4().hex[:12]
        try:
            result = await self._call_openai(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url)
            return {
                "success": True,
                "result": {
                    "text": result["text"],
                    "model": self._model_name,
                    "provider": "openai",
                    "request_id": request_id,
                    "finish_reason": "stop",
                    "execution": {"runtime": "openai", "device": "", "memory_mb": 0},
                    "billing": {"input_units": result["input_units"], "output_units": result["output_units"]},
                    "trace": {"request_id": uuid.uuid4().hex[:12]},
                },
                "usage": {
                    "capability": "chat.generate",
                    "adapter_id": "openai",
                    "timestamp": __import__("datetime").datetime.now(),
                    "input_units": result["input_units"],
                    "output_units": result["output_units"],
                    "cost": None,
                    "provider_id": "openai",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_stream(self, request: dict):
        from services.ai_gateway.interfaces.adapter import StreamChunk
        prompt = request.get("payload", {}).get("prompt", "")
        async for chunk in self._stream_openai(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url):
            yield chunk

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        caps = frozenset(self._metadata.get("capabilities", ()))
        return required_capabilities.issubset(caps)

    def get_capabilities(self) -> tuple[str, ...]:
        return ("model.text.generate", "model.code.generate", "model.embed.create")

    async def health_check(self):
        try:
            import httpx
            async with __import__("httpx").AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10.0,
                )
                return {
                    "healthy": response.status_code == 200,
                    "provider": "openai",
                    "model": self._model_name,
                    "details": {"status_code": response.status_code},
                }
        except Exception as e:
            return {"healthy": False, "provider": "openai", "details": {"error": str(e)}}