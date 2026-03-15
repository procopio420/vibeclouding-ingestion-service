"""Tests for architecture trigger service."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.architecture_trigger_service import ArchitectureTriggerService
from app.db import get_session, DiscoverySessionModel, ProjectModel


class TestArchitectureTriggerService:
    """Tests for ArchitectureTriggerService."""

    @pytest.fixture
    def setup_project_and_session(self):
        """Create a test project and discovery session."""
        session = get_session()
        try:
            project_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            now = datetime.utcnow()

            project = ProjectModel(
                id=project_id,
                name="Test Project",
                status="collecting_initial_context"
            )
            session.add(project)

            discovery_session = DiscoverySessionModel(
                id=session_id,
                project_id=project_id,
                state="collecting_initial_context",
                readiness_status="not_ready",
                started_at=now,
                updated_at=now,
                last_transition_at=now,
                eligible_for_architecture=False,
                architecture_triggered=False
            )
            session.add(discovery_session)
            session.commit()

            yield project_id, session_id

            session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).delete()
            session.query(ProjectModel).filter(
                ProjectModel.id == project_id
            ).delete()
            session.commit()
        finally:
            session.close()

    def test_is_eligible_not_ready(self, setup_project_and_session):
        """Test that project not ready for architecture returns False."""
        project_id, _ = setup_project_and_session
        assert ArchitectureTriggerService.is_eligible(project_id) is False

    def test_is_eligible_ready_for_architecture(self, setup_project_and_session):
        """Test that project ready for architecture returns True."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            session.commit()
        finally:
            session.close()

        assert ArchitectureTriggerService.is_eligible(project_id) is True

    def test_is_eligible_already_triggered(self, setup_project_and_session):
        """Test that already triggered project returns False."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            discovery_session.architecture_triggered = True
            session.commit()
        finally:
            session.close()

        assert ArchitectureTriggerService.is_eligible(project_id) is False

    def test_is_eligible_no_session(self):
        """Test that non-existent project returns False."""
        assert ArchitectureTriggerService.is_eligible("non-existent-id") is False

    @patch('app.services.architecture_trigger_service.requests.post')
    def test_trigger_sends_webhook(self, mock_post, setup_project_and_session):
        """Test that trigger sends webhook successfully."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            session.commit()
        finally:
            session.close()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        result = ArchitectureTriggerService.trigger(project_id)

        assert result["success"] is True
        mock_post.assert_called_once()

    @patch('app.services.architecture_trigger_service.requests.post')
    def test_trigger_idempotent(self, mock_post, setup_project_and_session):
        """Test that trigger is idempotent - doesn't send twice."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            discovery_session.architecture_triggered = True
            discovery_session.architecture_triggered_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

        result = ArchitectureTriggerService.trigger(project_id)

        assert result["success"] is False
        assert result.get("skipped") is True
        mock_post.assert_not_called()

    @patch('app.services.architecture_trigger_service.requests.post')
    def test_trigger_updates_db_fields(self, mock_post, setup_project_and_session):
        """Test that trigger updates DB fields correctly."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            session.commit()
        finally:
            session.close()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        ArchitectureTriggerService.trigger(project_id)

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            assert discovery_session.architecture_triggered is True
            assert discovery_session.eligible_for_architecture is True
            assert discovery_session.architecture_trigger_status == "success"
            assert discovery_session.architecture_triggered_at is not None
        finally:
            session.close()

    @patch('app.services.architecture_trigger_service.requests.post')
    def test_trigger_handles_webhook_failure(self, mock_post, setup_project_and_session):
        """Test that trigger handles webhook failure gracefully."""
        project_id, _ = setup_project_and_session

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "ready_for_architecture"
            session.commit()
        finally:
            session.close()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = ArchitectureTriggerService.trigger(project_id)

        assert result["success"] is False
        assert "500" in result.get("error", "")

    def test_trigger_if_eligible_convenience(self, setup_project_and_session):
        """Test the convenience method trigger_if_eligible."""
        project_id, _ = setup_project_and_session
        result = ArchitectureTriggerService.trigger_if_eligible(project_id)
        assert result.get("skipped") is True
