"""Tests for ApprovalRequest domain model."""

from datetime import UTC, datetime, timedelta

from runtime.domain.approval_request import ApprovalRequest, ApprovalStatus, RiskLevel


class TestApprovalRequest:
    def test_valid_request_passes_validation(self) -> None:
        req = ApprovalRequest(
            approval_id="apr-1",
            execution_id="exec-1",
            agent_instance_id="a-1",
            action="send_mass_email",
            risk_level=RiskLevel.HIGH,
        )
        errors = req.validate()
        assert len(errors) == 0
        assert req.is_valid is True

    def test_missing_required_fields_fails(self) -> None:
        req = ApprovalRequest(
            approval_id="",
            execution_id="",
            agent_instance_id="a-1",
            action="",
            risk_level=RiskLevel.LOW,
        )
        errors = req.validate()
        assert len(errors) >= 3

    def test_initial_status_is_pending(self) -> None:
        req = ApprovalRequest(
            approval_id="apr-1",
            execution_id="exec-1",
            agent_instance_id="a-1",
            action="delete_records",
            risk_level=RiskLevel.HIGH,
        )
        assert req.status == ApprovalStatus.PENDING
        assert req.is_decided is False

    def test_approved_status_is_decided(self) -> None:
        req = ApprovalRequest(
            approval_id="apr-1",
            execution_id="exec-1",
            agent_instance_id="a-1",
            action="send_email",
            risk_level=RiskLevel.MEDIUM,
            status=ApprovalStatus.APPROVED,
            approved_by="user-42",
        )
        assert req.is_decided is True

    def test_expired_check(self) -> None:
        past = datetime(2025, 1, 1, tzinfo=UTC)
        req = ApprovalRequest(
            approval_id="apr-1",
            execution_id="exec-1",
            agent_instance_id="a-1",
            action="test",
            risk_level=RiskLevel.LOW,
            created_at=past,
            expires_at=past + timedelta(hours=1),
        )
        assert req.is_expired is True
