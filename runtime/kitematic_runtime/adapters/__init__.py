"""Concrete adapters bridging KitematicRuntime ABI to existing services.

These adapters implement the 4 ABI protocols using existing service implementations.
The ABI protocols (PolicyEvaluator, IntentRouter, ToolGateway, StatePersistence)
are the canonical interfaces. Adapters translate between ABI and service layers.
"""

from runtime.kitematic_runtime.adapters.checkpoint_adapter import CheckpointPersistenceAdapter
from runtime.kitematic_runtime.adapters.policy_adapter import PolicyEngineAdapter
from runtime.kitematic_runtime.adapters.simple_router import SimpleIntentRouter

__all__ = [
    "PolicyEngineAdapter",
    "SimpleIntentRouter",
    "CheckpointPersistenceAdapter",
]
