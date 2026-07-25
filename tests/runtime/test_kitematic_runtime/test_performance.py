"""Performance benchmark tests for KitematicRuntime.

Measures execution throughput, concurrent execution, checkpoint
round-trip, and event publisher fan-out under load.

These are validation benchmarks, not exhaustive stress tests.
"""

import asyncio
import time

import pytest

from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from control_plane.adapters.to_kernel.policy import PolicyEngineAdapter
from control_plane.adapters.to_kernel.router import SimpleIntentRouter
from runtime.kitematic_runtime.api.events import EventPublisher
from kernel.gateway import MCPToolGateway
from kernel.runtime import Intent, KitematicRuntime
from kernel.resources.tool_registry import ToolDefinition, ToolRegistry
from infrastructure.storage.checkpoint.in_memory import InMemoryCheckpointRepository
from control_plane.policy.engine import PolicyEngine


class _BenchmarkMCPClient:
    """MCP client that responds instantly for benchmarking."""

    def __init__(self, latency_ms: float = 0.0):
        self._latency = latency_ms
        self.call_count = 0

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.call_count += 1
        if self._latency > 0:
            await asyncio.sleep(self._latency / 1000.0)
        return {"result": "ok", "tool": tool_name}


@pytest.fixture
def benchmark_runtime():
    """Runtime with instant-responding MCP client for benchmarks."""
    engine = PolicyEngine()
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        tool_id="mcp.bench.query",
        mcp_server="bench-server",
        description="Benchmark tool",
    ))
    client = _BenchmarkMCPClient()
    gateway = MCPToolGateway(registry=reg)
    gateway.register_client("bench-server", client)

    runtime = KitematicRuntime(
        policy=PolicyEngineAdapter(engine),
        router=SimpleIntentRouter(reg),
        gateway=gateway,
        persistence=CheckpointPersistenceAdapter(InMemoryCheckpointRepository()),
    )
    return runtime, client


class TestSequentialPerformance:
    """Sequential execution throughput benchmarks."""

    @pytest.mark.asyncio
    async def test_sequential_10_intents(self, benchmark_runtime):
        """10 intents sequentially should complete in reasonable time."""
        runtime, client = benchmark_runtime
        intent = Intent(agent_id="agent-1", action="mcp.bench.query")

        start = time.time()
        for _ in range(10):
            result = await runtime.execute_intent(intent)
            assert result.success is True
        elapsed = time.time() - start

        assert client.call_count == 10
        assert elapsed < 5.0, f"10 sequential intents took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_throughput_sequential(self, benchmark_runtime):
        """Measure average latency for sequential execution."""
        runtime, client = benchmark_runtime
        intent = Intent(agent_id="agent-1", action="mcp.bench.query")

        start = time.time()
        for _ in range(20):
            await runtime.execute_intent(intent)
        elapsed = time.time() - start

        avg_ms = (elapsed / 20) * 1000
        assert avg_ms < 500, f"Avg latency {avg_ms:.1f}ms exceeds 500ms"


class TestConcurrentPerformance:
    """Concurrent execution benchmarks."""

    @pytest.mark.asyncio
    async def test_concurrent_5_intents(self, benchmark_runtime):
        """5 concurrent intents should all complete successfully."""
        runtime, client = benchmark_runtime
        intent = Intent(agent_id="agent-1", action="mcp.bench.query")

        results = await asyncio.gather(
            *[runtime.execute_intent(intent) for _ in range(5)],
        )
        assert all(r.success for r in results)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_concurrent_latency(self, benchmark_runtime):
        """Measure wall-clock time for 5 concurrent intents."""
        runtime, client = benchmark_runtime
        intent = Intent(agent_id="agent-1", action="mcp.bench.query")

        start = time.time()
        await asyncio.gather(
            *[runtime.execute_intent(intent) for _ in range(5)],
        )
        elapsed = time.time() - start

        assert elapsed < 3.0, f"5 concurrent intents took {elapsed:.2f}s"


class TestCheckpointRoundTrip:
    """Checkpoint save + restore performance."""

    @pytest.mark.asyncio
    async def test_checkpoint_round_trip(self, benchmark_runtime):
        """Checkpoints should save and restore in reasonable time."""
        runtime, client = benchmark_runtime

        # Execute and get checkpoint
        result = await runtime.execute_intent(
            Intent(agent_id="agent-1", action="mcp.bench.query")
        )
        assert result.checkpoint_id is not None

        # Restore from checkpoint
        start = time.time()
        state = await runtime.restore_from_checkpoint(result.checkpoint_id)
        elapsed = time.time() - start

        assert state is not None
        assert state["intent_action"] == "mcp.bench.query"
        assert elapsed < 1.0, f"Checkpoint restore took {elapsed:.2f}s"


class TestEventPublisherFanOut:
    """EventPublisher performance with multiple subscribers."""

    @pytest.mark.asyncio
    async def test_fan_out_10_subscribers(self):
        """Publishing to 10 subscribers should deliver to all."""
        pub = EventPublisher()
        queues = [pub.subscribe("exec-1") for _ in range(10)]

        await pub.publish("exec-1", {"event": "test"})

        for q in queues:
            msg = await asyncio.wait_for(q.get(), timeout=1.0)
            assert msg["event"] == "test"

    @pytest.mark.asyncio
    async def test_fan_out_latency(self):
        """Measure publish latency to N subscribers."""
        pub = EventPublisher()
        queues = [pub.subscribe("exec-1") for _ in range(10)]

        start = time.time()
        await pub.publish("exec-1", {"event": "latency_test"})
        elapsed = time.time() - start

        # Verify delivery
        for q in queues:
            msg = await asyncio.wait_for(q.get(), timeout=1.0)
            assert msg["event"] == "latency_test"

        assert elapsed < 1.0, f"Fan-out to 10 took {elapsed:.2f}s"


class TestGatewayAuditTrail:
    """Audit trail integrity under load."""

    @pytest.mark.asyncio
    async def test_audit_log_after_n_calls(self, benchmark_runtime):
        """N gateway calls produce exactly N audit entries."""
        runtime, client = benchmark_runtime

        # Access the gateway from runtime internals
        intent = Intent(agent_id="agent-1", action="mcp.bench.query")
        for _ in range(5):
            await runtime.execute_intent(intent)

        # Each execution produces one gateway access
        gateway = runtime._gateway
        assert len(gateway.audit_log) == 5
        assert all(e.success for e in gateway.audit_log)
