"""Google Gemini model adapter."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from services.ai_gateway.interfaces.adapter import StreamChunk


async def _call_gemini(prompt: str, model: str, api_key: str, base_url: str) -> dict:
    import httpx
    url = f"{base_url}/models/{model}:generateContent"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return {
            "text": text,
            "input_units": usage.get("promptTokenCount", len(prompt)),
            "output_units": usage.get("candidatesTokenCount", len(text)),
        }


async def _stream_gemini(prompt: str, model: str, api_key: str, base_url: str):
    import httpx
    import json
    from services.ai_gateway.interfaces.adapter import StreamChunk
    url = f"{base_url}/models/{model}:streamGenerateContent"
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            url,
            params={"key": api_key, "alt": "sse"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
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
                    candidates = chunk.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            text = p.get("text", "")
                            if text:
                                yield StreamChunk(content=text)
                except json.JSONDecodeError:
                    continue


class GeminiAdapter:
    """Google Gemini model adapter."""

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key: str = "",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._metadata = {
            "adapter_id": "gemini",
            "name": "Google Gemini",
            "version": "1.0",
            "capabilities": ("model.text.generate", "model.code.generate", "model.vision"),
            "provider": "google",
            "status": "active",
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    async def execute(self, request: dict) -> dict:
        import uuid
        prompt = request.get("payload", {}).get("prompt", "")
        request_id = uuid.uuid4().hex[:12]
        try:
            result = await _call_gemini(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url)
            return {
                "success": True,
                "result": {
                    "text": result["text"],
                    "model": self._model_name,
                    "provider": "google",
                    "request_id": uuid.uuid4().hex[:12],
                    "finish_reason": "stop",
                    "execution": {"runtime": "gemini", "device": "", "memory_mb": 0},
                    "billing": {"input_units": result["input_units"], "output_units": result["output_units"]},
                    "trace": {"request_id": uuid.uuid4().hex[:12]},
                },
                "usage": {
                    "capability": "chat.generate",
                    "adapter_id": "gemini",
                    "timestamp": str(datetime.now()),
                    "input_units": result["input_units"],
                    "output_units": result["output_units"],
                    "cost": None,
                    "provider_id": "google",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_stream(self, request: dict):
        from services.ai_gateway.interfaces.adapter import StreamChunk
        prompt = request.get("payload", {}).get("prompt", "")
        async for chunk in self._stream_gemini(prompt, model=self._model_name, api_key=self._api_key, base_url=self._base_url):
            yield chunk

    async def health_check(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    params={"key": self._api_key},
                    timeout=10.0,
                )
                return {
                    "healthy": response.status_code == 200,
                    "provider": "google",
                    "model": self._model_name,
                    "details": {"status_code": response.status_code},
                }
        except Exception as e:
            return {"healthy": False, "provider": "google", "details": {"error": str(e)}}

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        caps = frozenset(self._metadata.get("capabilities", ()))
        return required_capabilities.issubset(caps)

    def get_capabilities(self) -> tuple[str, ...]:
        return ("model.text.generate", "model.code.generate", "model.vision")

    @property
    def _model_name(self) -> str:
        return "gemini-2.0-flash"

    @property
    def _api_key(self) -> str:
        return ""

    @property
    def _base_url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta"