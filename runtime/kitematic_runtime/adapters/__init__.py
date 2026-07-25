"""Concrete adapters bridging KitematicRuntime ABI to existing services.

These adapters implement the 4 ABI protocols using existing service implementations.
The ABI protocols (PolicyEvaluator, IntentRouter, ToolGateway, StatePersistence)
are the canonical interfaces. Adapters translate between ABI and service layers.
"""

from control_plane.adapters.to_kernel.checkpoint import CheckpointPersistenceAdapter
from control_plane.adapters.to_kernel.policy import PolicyEngineAdapter
from control_plane.adapters.to_kernel.router import SimpleIntentRouter

__all__ = [
    "PolicyEngineAdapter",
    "SimpleIntentRouter",
    "CheckpointPersistenceAdapter",
]
