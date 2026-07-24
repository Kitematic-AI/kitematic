"""MCP (Model Context Protocol) tool adapter - simplified baseline."""

import time
from collections.abc import AsyncIterator
from datetime import datetime

from runtime.domain.runtime_event import StreamChunk
from services.ai_gateway.adapters.mcp.interfaces.mcp_client import MCPClient
from services.ai_gateway.domain.adapter_metadata import AdapterMetadata
from services.ai_gateway.domain.gateway_request import GatewayRequest


class MCPAdapter:
    """MCP (Model Context Protocol) tool adapter - simplified baseline."""

    def __init__(
        self,
        client: MCPClient,
        metadata: AdapterMetadata,
    ) -> None:
        self._client = client
        self._metadata = metadata

    @property
    def metadata(self) -> dict:
        return {
            "adapter_id": self._metadata.adapter_id,
            "name": self._metadata.name,
            "version": self._metadata.version,
            "capabilities": tuple(self._metadata.capabilities),
            "provider": self._metadata.provider,
            "status": self._metadata.status.value if hasattr(self._metadata.status, "value") else str(self._metadata.status),
        }

    async def execute(self, request: GatewayRequest) -> dict:
        correlation_id = request.metadata.get("trace_id", "")
        start = time.perf_counter()
        try:
            result = await self._client.call_tool(request.capability, request.payload)
        except Exception:
            raise

        elapsed = (time.perf_counter() - start) * 1000
        return {
            "success": True,
            "result": result,
            "usage": {
                "capability": request.capability,
                "adapter_id": self._metadata.adapter_id,
                "timestamp": datetime.now(),
                "input_units": result.get("input_units", 0),
                "output_units": result.get("output_units", 0),
                "cost": result.get("cost"),
                "provider_id": self._metadata.provider,
                "tenant_id": request.metadata.get("tenant_id"),
                "trace_id": request.metadata.get("trace_id"),
                "request_id": request.metadata.get("request_id"),
            },
        }

    async def execute_stream(
        self, request: GatewayRequest
    ) -> AsyncIterator:
        prompt = request.payload.get("prompt", "")
        result = await self._client.call_tool(request.capability, request.payload)
        text = result.get("text", prompt)
        yield StreamChunk(content=text)
        yield StreamChunk(content=None, finish_reason="stop")

    async def health_check(self) -> dict:
        try:
            info = await self._client.get_server_info()
            return {
                "healthy": True,
                "provider": self._metadata.provider,
                "details": {"server_info": str(info)},
            }
        except Exception as e:
            return {"healthy": False, "provider": self._metadata.provider, "details": {"error": str(e)}}

    def supports(self, required_capabilities: frozenset[str]) -> bool:
        caps = frozenset(self._metadata.capabilities)
        return required_capabilities.issubset(caps)

    def get_capabilities(self) -> tuple[str, ...]:
        return tuple(self._metadata.capabilities)
