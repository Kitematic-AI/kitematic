"""FileSystem CheckpointRepository implementation.

Stores checkpoints as individual JSON files on disk.
Execution index maintained as a separate index file for fast querying.
Atomic writes via temp file + rename to prevent corruption.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from runtime.domain.checkpoint import Checkpoint, CheckpointTrigger
from services.checkpoint.interfaces.checkpoint_repository import CheckpointRepository


class FileSystemCheckpointRepository(CheckpointRepository):
    """File-system backed checkpoint store with atomic writes.

    Storage layout:
        base_dir/
        ├── checkpoints/
        │   ├── cp-abc123.json
        │   ├── cp-def456.json
        │   └── ...
        └── index.json
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._checkpoints_dir = self._base / "checkpoints"
        self._index_path = self._base / "index.json"
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._lock = False

    def _checkpoint_path(self, checkpoint_id: str) -> Path:
        return self._checkpoints_dir / f"{checkpoint_id}.json"

    def _load_index(self) -> dict[str, list[str]]:
        if not self._index_path.exists():
            return {}
        try:
            with open(self._index_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_index(self, index: dict[str, list[str]]) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(index, f, sort_keys=True)
        tmp.replace(self._index_path)

    def _checkpoint_to_dict(self, cp: Checkpoint) -> dict[str, Any]:
        return {
            "checkpoint_id": cp.checkpoint_id,
            "execution_id": cp.execution_id,
            "version": cp.version,
            "trigger_reason": cp.trigger_reason.value,
            "checkpoint_hash": cp.checkpoint_hash,
            "schema_version": cp.schema_version,
            "parent_checkpoint_id": cp.parent_checkpoint_id,
            "agent_state_ref": cp.agent_state_ref,
            "memory_refs": list(cp.memory_refs),
            "tool_history": [
                {k: v for k, v in th.items()} for th in cp.tool_history
            ],
            "created_at": cp.created_at.isoformat() if cp.created_at else None,
        }

    def _dict_to_checkpoint(self, data: dict[str, Any]) -> Checkpoint:
        from datetime import datetime

        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])

        return Checkpoint(
            checkpoint_id=data["checkpoint_id"],
            execution_id=data["execution_id"],
            version=data["version"],
            trigger_reason=CheckpointTrigger(data["trigger_reason"]),
            checkpoint_hash=data["checkpoint_hash"],
            schema_version=data.get("schema_version", "1.0"),
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
            agent_state_ref=data.get("agent_state_ref"),
            memory_refs=tuple(data.get("memory_refs", [])),
            tool_history=tuple(
                dict(th) for th in data.get("tool_history", [])
            ),
            created_at=created_at,
        )

    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
        stored = copy.deepcopy(checkpoint)

        # Write checkpoint file atomically
        data = self._checkpoint_to_dict(stored)
        dest = self._checkpoint_path(stored.checkpoint_id)
        tmp = dest.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, sort_keys=True, default=str)
        tmp.replace(dest)

        # Update execution index
        index = self._load_index()
        exec_id = stored.execution_id
        if exec_id not in index:
            index[exec_id] = []
        if stored.checkpoint_id not in index[exec_id]:
            index[exec_id].append(stored.checkpoint_id)
        self._save_index(index)

        return copy.deepcopy(stored)

    async def get(self, checkpoint_id: str) -> Checkpoint | None:
        path = self._checkpoint_path(checkpoint_id)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            checkpoint = self._dict_to_checkpoint(data)
            return copy.deepcopy(checkpoint)
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    async def list_by_execution(self, execution_id: str) -> list[Checkpoint]:
        index = self._load_index()
        ids = index.get(execution_id, [])
        checkpoints: list[Checkpoint] = []
        for cid in ids:
            cp = await self.get(cid)
            if cp is not None:
                checkpoints.append(cp)
        checkpoints.sort(key=lambda cp: (cp.version, cp.checkpoint_id))
        return [copy.deepcopy(cp) for cp in checkpoints]

    async def get_latest(self, execution_id: str) -> Checkpoint | None:
        checkpoints = await self.list_by_execution(execution_id)
        if not checkpoints:
            return None
        return copy.deepcopy(max(checkpoints, key=lambda cp: cp.version))
