"""EventPublisher — backward-compatible re-export.

The concrete InMemoryEventPublisher has moved to runtime.events.memory.
This module provides a backward-compatible alias so existing imports
continue to work without changes.

Deprecated: import from runtime.events instead of runtime.api.events.
"""

from runtime.kitematic_runtime.events.memory import InMemoryEventPublisher

# Backward-compatible alias
# Deprecated: import from runtime.events.memory instead
EventPublisher = InMemoryEventPublisher

__all__ = [
    "EventPublisher",
    "InMemoryEventPublisher",
]
