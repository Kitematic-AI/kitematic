"""Tests for PluginRuntimeRecord."""

from datetime import datetime

from core.domain.plugin_runtime import PluginRuntimeRecord, PluginRuntimeState


class TestPluginRuntimeRecord:
    def test_default_state_is_created(self) -> None:
        record = PluginRuntimeRecord(name="test", version="1.0.0")
        assert record.state == PluginRuntimeState.CREATED
        assert record.loaded_at is None
        assert record.error is None

    def test_set_running_state(self) -> None:
        record = PluginRuntimeRecord(
            name="test",
            version="1.0.0",
            state=PluginRuntimeState.RUNNING,
            loaded_at=datetime(2026, 7, 25),
        )
        assert record.state == PluginRuntimeState.RUNNING
        assert record.loaded_at == datetime(2026, 7, 25)

    def test_failed_state_with_error(self) -> None:
        record = PluginRuntimeRecord(
            name="test",
            version="1.0.0",
            state=PluginRuntimeState.FAILED,
            error="import failed",
        )
        assert record.error == "import failed"
        assert record.state == PluginRuntimeState.FAILED

    def test_health_update(self) -> None:
        record = PluginRuntimeRecord(name="test", version="1.0.0")
        record.state = PluginRuntimeState.RUNNING
        record.last_health_check = datetime(2026, 7, 25, 12, 0, 0)
        assert record.last_health_check is not None
        assert record.state == PluginRuntimeState.RUNNING

    def test_stopped_transition(self) -> None:
        record = PluginRuntimeRecord(
            name="test",
            version="1.0.0",
            state=PluginRuntimeState.STOPPED,
        )
        assert record.state.value == "stopped"

    def test_metadata_roundtrip(self) -> None:
        record = PluginRuntimeRecord(
            name="test",
            version="1.0.0",
            metadata={"entrypoint": {"module": "test", "class": "Test"}},
        )
        assert record.metadata["entrypoint"]["module"] == "test"
