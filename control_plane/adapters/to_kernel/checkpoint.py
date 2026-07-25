"""CheckpointPersistenceAdapter — bridges ABI StatePersistence to CheckpointRepository.

Embeds serialized state directly in checkpoint.agent_state_ref as JSON.
This avoids a separate state storage layer while maintaining durability
through the checkpoint repository.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from core.domain.checkpoint import Checkpoint, CheckpointTrigger
from kernel.exceptions import CheckpointPersistenceError
from kernel.runtime import StatePersistence
from core.contracts.checkpoint_repository import CheckpointRepository


class CheckpointPersistenceAdapter(StatePersistence):
    """Concrete adapter: ABI StatePersistence → CheckpointRepository.

    Translates:
      - save(execution_id, state) → Checkpoint domain object with embedded state
      - restore(checkpoint_id) → state dict parsed from agent_state_ref

    State is embedded in the checkpoint's agent_state_ref field as JSON.
    This eliminates the need for a separate state store while maintaining
    durability through the checkpoint repository.
    """

    def __init__(self, repo: CheckpointRepository) -> None:
        self._repo = repo
        self._version_counter: dict[str, int] = {}

    async def save(self, execution_id: str, state: dict[str, Any]) -> str:
        """Save execution state as a checkpoint.

        Serializes state to JSON and embeds it in agent_state_ref.
        Returns checkpoint_id.
        Raises CheckpointPersistenceError if save fails.
        """
        try:
            checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"

            current_version = self._version_counter.get(execution_id, 0) + 1
            self._version_counter[execution_id] = current_version

            state_json = json.dumps(state, sort_keys=True, default=str)
            state_hash = hashlib.sha256(state_json.encode()).hexdigest()[:16]

            checkpoint = Checkpoint(
                checkpoint_id=checkpoint_id,
                execution_id=execution_id,
                version=current_version,
                trigger_reason=CheckpointTrigger.STEP_COMPLETE,
                checkpoint_hash=state_hash,
                agent_state_ref=state_json,
                created_at=datetime.now(UTC),
            )

            errors = checkpoint.validate()
            if errors:
                raise CheckpointPersistenceError(
                    operation="save",
                    reason=f"Invalid checkpoint: {errors}",
                )

            await self._repo.save(checkpoint)
            return checkpoint_id

        except CheckpointPersistenceError:
            raise
        except Exception as e:
            raise CheckpointPersistenceError(
                operation="save",
                reason=str(e),
            )

    async def restore(self, checkpoint_id: str) -> dict[str, Any]:
        """Restore execution state from checkpoint.

        Parses state from checkpoint.agent_state_ref (embedded JSON).
        Raises CheckpointPersistenceError if restore fails.
        """
        try:
            checkpoint = await self._repo.get(checkpoint_id)
            if checkpoint is None:
                raise CheckpointPersistenceError(
                    operation="restore",
                    reason=f"Checkpoint not found: {checkpoint_id}",
                )

            state_json = checkpoint.agent_state_ref
            if state_json is None:
                raise CheckpointPersistenceError(
                    operation="restore",
                    reason=f"Checkpoint '{checkpoint_id}' contains no state",
                )

            return cast(dict[str, Any], json.loads(state_json))

        except json.JSONDecodeError as e:
            raise CheckpointPersistenceError(
                operation="restore",
                reason=f"Corrupted state in checkpoint '{checkpoint_id}': {e}",
            )
        except CheckpointPersistenceError:
            raise
        except Exception as e:
            raise CheckpointPersistenceError(
                operation="restore",
                reason=str(e),
            )
