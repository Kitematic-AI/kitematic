from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservabilityContext:
    """Unified correlation context shared across logger, tracer, and metrics.

    Ensures execution_id, tenant_id, agent_id, and intent_action
    are consistent across all observability outputs for a single execution.
    """

    execution_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    intent_action: str = ""
