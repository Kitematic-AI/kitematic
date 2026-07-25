"""Tests for Checkpoint domain model."""

from core.domain.checkpoint import Checkpoint, CheckpointTrigger


class TestCheckpoint:
    def test_valid_checkpoint_passes_validation(self) -> None:
        cp = Checkpoint(
            checkpoint_id="cp-1",
            execution_id="exec-1",
            version=5,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="abc123def456",
        )
        errors = cp.validate()
        assert len(errors) == 0
        assert cp.is_valid is True

    def test_missing_required_fields_fails(self) -> None:
        cp = Checkpoint(
            checkpoint_id="",
            execution_id="",
            version=0,
            trigger_reason=CheckpointTrigger.STEP_COMPLETE,
            checkpoint_hash="",
        )
        errors = cp.validate()
        assert len(errors) >= 3

    def test_negative_version_fails(self) -> None:
        cp = Checkpoint(
            checkpoint_id="cp-1",
            execution_id="exec-1",
            version=-1,
            trigger_reason=CheckpointTrigger.ERROR_RECOVERY,
            checkpoint_hash="hash",
        )
        errors = cp.validate()
        assert any("version" in e for e in errors)

    def test_all_triggers(self) -> None:
        triggers = [
            CheckpointTrigger.STEP_COMPLETE,
            CheckpointTrigger.BEFORE_TOOL_CALL,
            CheckpointTrigger.AFTER_TOOL_CALL,
            CheckpointTrigger.ERROR_RECOVERY,
            CheckpointTrigger.PAUSE_REQUEST,
            CheckpointTrigger.BEFORE_IRREVERSIBLE,
        ]
        for t in triggers:
            assert t.value is not None
