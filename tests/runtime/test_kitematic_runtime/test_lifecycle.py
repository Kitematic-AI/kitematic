"""Tests for lifecycle hardening — stop(), shutdown(), close_all(), lifespan.

Verifies:
  - KitematicRuntime.stop() prevents new executions, is idempotent
  - EventPublisher.close_all() drains all subscribers
  - LoopController.shutdown() prevents new intents
  - FastAPI lifespan calls stop() + close_all() on shutdown
  - Backward compatibility: runtime without stop() behaves normally
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from api.rest.app import create_app
from api.events.publisher import EventPublisher
from kernel.resources.budget import ExecutionBudget
from kernel.lifecycle import LoopController
from kernel.observability.logging import RuntimeLogger
from kernel.observability.metrics import MetricsRegistry
from kernel.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)
from kernel.state import ExecutionState, RuntimeState

# ── Mock Implementations ─────────────────────────────────────────────


class MockPolicyEvaluator(PolicyEvaluator):
    def __init__(self, allow_intent: bool = True, allow_capability: bool = True):
        self._allow_intent = allow_intent
        self._allow_capability = allow_capability

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        return self._allow_intent, None

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return self._allow_capability, None


class MockIntentRouter(IntentRouter):
    async def route_intent(self, intent: Intent) -> ExecutionPath:
        return ExecutionPath(tool="mock.tool", adapter="mock")


class MockToolGateway(ToolGateway):
    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        return ToolResult(success=True, data={"ok": True})


class MockStatePersistence(StatePersistence):
    async def save(self, execution_id: str, state: dict) -> str:
        return "cp-1"

    async def restore(self, checkpoint_id: str) -> dict:
        return {}


def make_runtime(
    logger=None, metrics=None,
) -> KitematicRuntime:
    return KitematicRuntime(
        policy=MockPolicyEvaluator(),
        router=MockIntentRouter(),
        gateway=MockToolGateway(),
        persistence=MockStatePersistence(),
        logger=logger,
        metrics=metrics,
    )


def make_loop(logger=None, metrics=None):
    runtime = make_runtime(logger=logger, metrics=metrics)
    budget = ExecutionBudget(max_steps=10)
    return LoopController(runtime, budget, logger=logger, metrics=metrics)


# ═══════════════════════════════════════════════════════════════════════
# 1. KitematicRuntime.stop()
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeStop:
    """Verify KitematicRuntime.stop() behavior."""

    @pytest.mark.asyncio
    async def test_stop_sets_stopping_flag(self):
        runtime = make_runtime()
        assert runtime.state == RuntimeState.RUNNING
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_prevents_new_executions(self):
        runtime = make_runtime()
        await runtime.stop()
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert "stopped" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        runtime = make_runtime()
        await runtime.stop()
        await runtime.stop()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED
        # After third stop, still rejecting
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_stop_allows_inflight_to_complete(self):
        """In-flight executions are not cancelled by stop()."""
        runtime = make_runtime()
        task = asyncio.create_task(
            runtime.execute_intent(Intent(agent_id="a1", action="test"))
        )
        await asyncio.sleep(0.01)
        await runtime.stop()
        result = await task
        assert result.success is True

    @pytest.mark.asyncio
    async def test_stop_with_observability_logs(self, capsys):
        logger = RuntimeLogger("kitematic.test.lifecycle")
        metrics = MetricsRegistry()
        runtime = make_runtime(logger=logger, metrics=metrics)
        await runtime.stop()
        assert metrics.get_counter("runtime.shutdown.count") == 1

        captured = capsys.readouterr()
        logs = [json.loads(line) for line in captured.out.strip().split("\n") if line.strip()]
        messages = [l["message"] for l in logs]
        assert "Runtime stopped" in messages

    @pytest.mark.asyncio
    async def test_stop_without_observability_works(self):
        runtime = make_runtime()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED


# ═══════════════════════════════════════════════════════════════════════
# 1b. RuntimeState Drain Lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestRuntimeDrain:
    """Verify RuntimeState transitions: RUNNING → DRAINING → STOPPED."""

    @pytest.mark.asyncio
    async def test_initial_state_is_running(self):
        runtime = make_runtime()
        assert runtime.state == RuntimeState.RUNNING

    @pytest.mark.asyncio
    async def test_drain_transitions_to_draining(self):
        runtime = make_runtime()
        await runtime.drain()
        assert runtime.state == RuntimeState.DRAINING

    @pytest.mark.asyncio
    async def test_drain_rejects_new_executions(self):
        runtime = make_runtime()
        await runtime.drain()
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert "draining" in result.error.lower()

    @pytest.mark.asyncio
    async def test_drain_then_stop(self):
        runtime = make_runtime()
        await runtime.drain()
        assert runtime.state == RuntimeState.DRAINING
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_from_running(self):
        runtime = make_runtime()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED

    @pytest.mark.asyncio
    async def test_drain_is_idempotent(self):
        runtime = make_runtime()
        await runtime.drain()
        await runtime.drain()
        await runtime.drain()
        assert runtime.state == RuntimeState.DRAINING

    @pytest.mark.asyncio
    async def test_stop_after_drain(self):
        runtime = make_runtime()
        await runtime.drain()
        await runtime.stop()
        assert runtime.state == RuntimeState.STOPPED
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_drain_with_observability(self, capsys):
        logger = RuntimeLogger("kitematic.test.drain")
        metrics = MetricsRegistry()
        runtime = make_runtime(logger=logger, metrics=metrics)
        await runtime.drain()
        assert runtime.state == RuntimeState.DRAINING
        result = await runtime.execute_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False
        assert "draining" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# 2. EventPublisher.close_all()
# ═══════════════════════════════════════════════════════════════════════


class TestEventPublisherCloseAll:
    """Verify EventPublisher.close_all() behavior."""

    @pytest.mark.asyncio
    async def test_close_all_clears_all_subscribers(self):
        pub = EventPublisher()
        pub.subscribe("exec-1")
        pub.subscribe("exec-2")
        pub.subscribe("exec-2")
        assert pub.subscriber_count("exec-1") == 1
        assert pub.subscriber_count("exec-2") == 2

        pub.close_all()
        assert pub.active_executions == []
        assert pub.subscriber_count("exec-1") == 0
        assert pub.subscriber_count("exec-2") == 0

    @pytest.mark.asyncio
    async def test_close_all_sends_sentinels(self):
        pub = EventPublisher()
        q1 = pub.subscribe("exec-1")
        q2 = pub.subscribe("exec-2")

        pub.close_all()

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1 is None
        assert r2 is None

    @pytest.mark.asyncio
    async def test_close_all_empty_is_noop(self):
        pub = EventPublisher()
        pub.close_all()
        assert pub.active_executions == []

    @pytest.mark.asyncio
    async def test_close_all_is_idempotent(self):
        pub = EventPublisher()
        pub.subscribe("exec-1")
        pub.close_all()
        pub.close_all()
        assert pub.active_executions == []


# ═══════════════════════════════════════════════════════════════════════
# 3. LoopController.shutdown()
# ═══════════════════════════════════════════════════════════════════════


class TestLoopShutdown:
    """Verify LoopController.shutdown() behavior."""

    @pytest.mark.asyncio
    async def test_shutdown_prevents_new_intents(self):
        loop = make_loop()
        await loop.shutdown()
        result = await loop.run_intent(Intent(agent_id="a1", action="x"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self):
        loop = make_loop()
        await loop.shutdown()
        await loop.shutdown()
        await loop.shutdown()
        assert loop.state == RuntimeState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_with_logger(self, capsys):
        logger = RuntimeLogger("kitematic.test.loop.shutdown")
        loop = make_loop(logger=logger)
        await loop.shutdown()
        captured = capsys.readouterr()
        logs = [json.loads(line) for line in captured.out.strip().split("\n") if line.strip()]
        messages = [l["message"] for l in logs]
        assert "Loop shutting down" in messages


# ═══════════════════════════════════════════════════════════════════════
# 4. FastAPI Lifespan
# ═══════════════════════════════════════════════════════════════════════


class TestFastAPILifecycle:
    """Verify FastAPI lifespan calls stop() + close_all() on shutdown."""

    def test_lifespan_shutdown_calls_stop(self):
        runtime = make_runtime()
        publisher = EventPublisher()
        publisher.subscribe("exec-1")

        app = create_app(runtime, event_publisher=publisher)

        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200

        # After lifespan shutdown:
        assert runtime.state == RuntimeState.STOPPED
        assert publisher.active_executions == []

    def test_lifespan_startup_sets_start_time(self):
        runtime = make_runtime()
        publisher = EventPublisher()
        app = create_app(runtime, event_publisher=publisher)

        with TestClient(app) as client:
            assert hasattr(app.state, "startup_time")
            assert app.state.startup_time is not None


# ═══════════════════════════════════════════════════════════════════════
# 5. Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════


class TestBackwardCompatLifecycle:
    """Verify runtime without stop() behaves exactly as before."""

    @pytest.mark.asyncio
    async def test_runtime_without_stop_behaves_normal(self):
        runtime = make_runtime()
        result = await runtime.execute_intent(Intent(agent_id="a1", action="test"))
        assert result.success is True
        assert result.state == ExecutionState.COMPLETED
        assert result.error is None

    @pytest.mark.asyncio
    async def test_loop_without_shutdown_behaves_normal(self):
        loop = make_loop()
        result = await loop.run_intent(Intent(agent_id="a1", action="test"))
        assert result.success is True

    def test_event_publisher_without_close_all_behaves_normal(self):
        pub = EventPublisher()
        assert pub.active_executions == []
        pub.subscribe("exec-1")
        assert pub.subscriber_count("exec-1") == 1
