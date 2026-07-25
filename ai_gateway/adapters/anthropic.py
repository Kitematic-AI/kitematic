"""Anthropic Claude model adapter."""

import uuid
from typing import Any

from core.contracts.adapter import StreamChunk


async def _call_anthropic(prompt: str, model: str, api_key: str, base_url: str) -> dict[str, Any]:
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        return {
            "text": text,
            "input_units": usage.get("input_tokens", len(prompt)),
            "output_units": usage.get("output_tokens", len(text)),
        }


async def _stream_anthropic(prompt: str, model: str, api_key: str, base_url: str):
    import json

    import httpx
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip() or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                try:
                    chunk = json.loads(line)
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield StreamChunk(content=text)
                    elif chunk.get("type") == "message_stop":
                        yield StreamChunk(content=None, finish_reason="stop")
                        return
                except json.JSONDecodeError:
                    continue


class AnthropicAdapter:
    def __init__(
        self,
        model_name: str = "claude-sonnet-4-20250514",
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._metadata = {
            "adapter_id": "anthropic",
            "name": "Anthropic Claude",
            "version": "1.0",
            "capabilities": ("model.text.generate", "model.code.generate", "model.reasoning"),
            "provider": "anthropic",
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    async def execute(self, request: dict) -> dict:
        prompt = request.get("payload", {}).get("prompt", "")
        request_id = uuid.uuid4().hex[:12]
        try:
            result = await self._call_anthropic(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url)
            return {
                "success": True,
                "result": {
                    "text": result["text"],
                    "model": self._model_name,
                    "provider": "anthropic",
                    "request_id": request_id,
                    "finish_reason": "stop",
                    "execution": {"runtime": "anthropic", "device": "", "memory_mb": 0},
                    "billing": {"input_units": result["input_units"], "output_units": result["output_units"]},
                    "trace": {"request_id": uuid.uuid4().hex[:12]},
                },
                "usage": {
                    "capability": "chat.generate",
                    "adapter_id": "anthropic",
                    "timestamp": __import__("datetime").datetime.now(),
                    "input_units": result["input_units"],
                    "output_units": result["output_units"],
                    "cost": None,
                    "provider_id": "anthropic",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_stream(self, request: dict):
        prompt = request.get("payload", {}).get("prompt", "")
        async for chunk in self._stream_anthropic(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url):
            yield chunk

    async def health_check(self):
        try:
            async with __import__("httpx").AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"x-api-key": self._api_key},
                    timeout=10.0,
                )
                return {
                    "healthy": response.status_code == 200,
                    "provider": "anthropic",
                    "model": self._model_name,
                    "details": {"status_code": response.status_code},
                }
        except Exception as e:
            return {"healthy": False, "provider": "anthropic", "details": {"error": str(e)}}

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        caps = frozenset(self._metadata.get("capabilities", ()))
        return required_capabilities.issubset(caps)

    def get_capabilities(self) -> tuple[str, ...]:
        return ("model.text.generate", "model.code.generate", "model.reasoning")

    async def health_check(self):
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"x-api-key": self._api_key},
                    timeout=10.0,
                )
                return {
                    "healthy": response.status_code == 200,
                    "provider": "anthropic",
                    "model": self._model_name,
                    "details": {"status_code": response.status_code},
                }
        except Exception as e:
            return {"healthy": False, "provider": "anthropic", "details": {"error": str(e)}}
