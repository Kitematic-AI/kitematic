"""Chaos Engineering — shared fixtures, guardrails, and result framework.

Every chaos experiment uses these fixtures to ensure:
  - Safety guardrails are checked before execution
  - Experiments are timed and produce structured results
  - Teardown restores state
  - Production environments are protected
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from runtime.kitematic_runtime.observability.metrics import MetricsRegistry
from runtime.kitematic_runtime.runtime import (
    ExecutionPath,
    Intent,
    IntentRouter,
    KitematicRuntime,
    PolicyEvaluator,
    StatePersistence,
    ToolGateway,
    ToolResult,
)

# ── Chaos Result Schema ─────────────────────────────────────────────────────


@dataclass
class ChaosResult:
    experiment_id: str
    scenario: str = ""
    level: str = "nightly"
    start_time: str = ""
    duration_seconds: float = 0.0
    expected_outcome: str = ""
    actual_outcome: str = ""
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    logs: str = ""
    recovery_rto_achieved: float | None = None
    recovery_rpo_achieved: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ── Guardrails ──────────────────────────────────────────────────────────────


def guard_production() -> None:
    """Skip chaos experiment if running in production without explicit override."""
    env = os.environ.get("KITEMATIC_ENV", "dev")
    if env == "prod" and not os.environ.get("KITEMATIC_CHAOS_PROD_ALLOWED"):
        pytest.skip("Chaos experiments blocked in production")


def guard_chaos_enabled() -> None:
    """Skip if chaos experiments are not explicitly enabled."""
    val = os.environ.get("KITEMATIC_CHAOS_ENABLED", "")
    if val.lower() not in ("1", "true", "yes"):
        pytest.skip("Chaos experiments require KITEMATIC_CHAOS_ENABLED=1")


def guard_level(min_level: str) -> None:
    """Skip if the configured chaos level is below the experiment's minimum."""
    level = os.environ.get("KITEMATIC_CHAOS_LEVEL", "nightly")
    levels = {"nightly": 0, "weekly": 1, "pre-release": 2, "manual": 3}
    if levels.get(level, 0) < levels.get(min_level, 0):
        pytest.skip(f"Requires chaos level >= {min_level} (current: {level})")


# ── Artifact Writer ─────────────────────────────────────────────────────────


def write_chaos_artifact(result: ChaosResult, output_dir: str = "chaos-results") -> None:
    """Write a chaos experiment result to disk as JSON."""
    artifact_dir = Path(output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{result.experiment_id}.json"
    path.write_text(result.to_json())


def write_chaos_summary(
    results: list[ChaosResult],
    output_dir: str = "chaos-results",
) -> dict[str, Any]:
    """Write a summary.json for a batch of experiments and return the summary dict."""
    artifact_dir = Path(output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    durations = [r.duration_seconds for r in results]
    mean_rt = (sum(durations) / len(durations)) if durations else 0.0
    variance = (
        sum((d - mean_rt) ** 2 for d in durations) / len(durations) if durations else 0.0
    )

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": os.environ.get("KITEMATIC_CHAOS_LEVEL", "nightly"),
        "total_experiments": total,
        "passed": passed,
        "failed": failed,
        "flaky": 0,
        "mean_recovery_time_ms": round(mean_rt * 1000, 2),
        "recovery_variance_ms": round(variance * 1000, 2),
        "chaos_success_rate": round(passed / total, 4) if total else 1.0,
        "experiments": [
            {
                "id": r.experiment_id,
                "passed": r.passed,
                "duration_s": round(r.duration_seconds, 2),
                "errors": r.errors[:3],
            }
            for r in results
        ],
    }

    path = artifact_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2, default=str))
    return summary


# ── Mock Components ─────────────────────────────────────────────────────────


class MockPolicyEvaluator(PolicyEvaluator):
    def __init__(self, allow: bool = True):
        self._allow = allow

    async def evaluate_intent(self, intent: Intent) -> tuple[bool, str | None]:
        return self._allow, (None if self._allow else "policy rejected by chaos experiment")

    async def check_capability(self, action: str, agent_id: str) -> tuple[bool, str | None]:
        return self._allow, (None if self._allow else "capability denied")


class MockIntentRouter(IntentRouter):
    async def route_intent(self, intent: Intent) -> ExecutionPath:
        return ExecutionPath(tool="chaos.mock.tool", adapter="chaos")


class MockToolGateway(ToolGateway):
    def __init__(self, should_fail: bool = False, latency: float = 0.0):
        self._should_fail = should_fail
        self._latency = latency

    async def access_tool(self, path: ExecutionPath, intent: Intent) -> ToolResult:
        if self._latency > 0:
            await _async_sleep(self._latency)
        if self._should_fail:
            return ToolResult(success=False, error="chaos gateway failure")
        return ToolResult(success=True, data={"output": "ok"})


class MockStatePersistence(StatePersistence):
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._ids: dict[str, str] = {}

    async def save(self, execution_id: str, state: dict) -> str:
        cp_id = f"cp-{execution_id}-{len(self._store)}"
        self._store[cp_id] = dict(state)
        self._ids[execution_id] = cp_id
        return cp_id

    async def restore(self, checkpoint_id: str) -> dict:
        state = self._store.get(checkpoint_id)
        if state is None:
            raise RuntimeError(f"Checkpoint not found: {checkpoint_id}")
        return dict(state)

    @property
    def checkpoint_count(self) -> int:
        return len(self._store)


async def _async_sleep(seconds: float) -> None:
    """Async sleep helper — uses asyncio.sleep if available, else time.sleep."""
    import asyncio
    await asyncio.sleep(seconds)


def make_runtime(
    policy: PolicyEvaluator | None = None,
    router: IntentRouter | None = None,
    gateway: ToolGateway | None = None,
    persistence: StatePersistence | None = None,
    metrics: MetricsRegistry | None = None,
) -> KitematicRuntime:
    return KitematicRuntime(
        policy=policy or MockPolicyEvaluator(),
        router=router or MockIntentRouter(),
        gateway=gateway or MockToolGateway(),
        persistence=persistence or MockStatePersistence(),
        metrics=metrics or MetricsRegistry(),
    )


# ── Chaos Experiment Fixture ────────────────────────────────────────────────


@pytest.fixture
def chaos_experiment(request):
    """Fixture that wraps a chaos experiment with guardrails, timing, and result capture.

    Usage:
        def test_something(chaos_experiment):
            result = chaos_experiment["result"]
            # ... run experiment ...
            result.passed = True
    """
    guard_production()
    guard_chaos_enabled()

    experiment_id = getattr(request.node, "chaos_id", request.node.name)
    scenario = getattr(request.node, "chaos_scenario", "")
    level = getattr(request.node, "chaos_level", "nightly")

    result = ChaosResult(
        experiment_id=experiment_id,
        scenario=scenario,
        level=level,
        start_time=datetime.now(UTC).isoformat(),
    )

    yield {
        "result": result,
        "metrics": MetricsRegistry(),
        "persistence": MockStatePersistence(),
    }

    now = datetime.now(UTC)
    start = datetime.fromisoformat(result.start_time)
    result.duration_seconds = (now - start).total_seconds()
    write_chaos_artifact(result)


# ── Recovery Validation ─────────────────────────────────────────────────────


def validate_recovery(
    result: ChaosResult,
    recovered: bool,
    rto_seconds: float = 30.0,
    rpo_records: int = 0,
    metrics_snapshot: dict | None = None,
) -> None:
    """Validate chaos experiment recovery against RTO/RPO criteria."""
    if recovered:
        result.recovery_rto_achieved = result.duration_seconds
        result.recovery_rpo_achieved = 0
        result.passed = result.duration_seconds <= rto_seconds and rpo_records == 0
        if not result.passed:
            if result.duration_seconds > rto_seconds:
                msg = f"RTO exceeded: {result.duration_seconds:.1f}s > {rto_seconds}s"
                result.errors.append(msg)
            if rpo_records > 0:
                result.errors.append(f"RPO exceeded: {rpo_records} records lost")
    else:
        result.recovery_rto_achieved = None
        result.recovery_rpo_achieved = rpo_records
        result.passed = False
        result.errors.append("Recovery did not occur")

    if metrics_snapshot:
        result.metrics_snapshot = metrics_snapshot
