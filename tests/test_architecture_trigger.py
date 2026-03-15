"""Tests for architecture trigger service (eligibility only; generation is in ArchitectureAgentService)."""
import pytest
import uuid
from datetime import datetime

from app.services.architecture_trigger_service import ArchitectureTriggerService
from app.db import get_session, DiscoverySessionModel, ProjectModel, ChecklistItemModel


class TestArchitectureTriggerService:
    """Tests for ArchitectureTriggerService.is_eligible (no webhook)."""

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

            session.query(ChecklistItemModel).filter(
                ChecklistItemModel.project_id == project_id
            ).delete()
            session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).delete()
            session.query(ProjectModel).filter(
                ProjectModel.id == project_id
            ).delete()
            session.commit()
        finally:
            session.close()

    def _add_repo_url(self, project_id: str, repo_url: str = "https://github.com/example/repo") -> None:
        """Add repo_exists checklist item so get_repo_url_for_panel returns the URL."""
        session = get_session()
        try:
            item = ChecklistItemModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                key="repo_exists",
                label="Repo",
                status="confirmed",
                priority="high",
                value=repo_url,
                updated_at=datetime.utcnow(),
            )
            session.add(item)
            session.commit()
        finally:
            session.close()

    def test_is_eligible_not_ready(self, setup_project_and_session):
        """Test that project not ready for architecture returns False."""
        project_id, _ = setup_project_and_session
        assert ArchitectureTriggerService.is_eligible(project_id) is False

    def test_is_eligible_ready_for_architecture(self, setup_project_and_session):
        """Test that project ready for architecture with repo returns True."""
        project_id, _ = setup_project_and_session
        self._add_repo_url(project_id)

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
        self._add_repo_url(project_id)

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

    def test_is_eligible_maybe_ready_with_repo(self, setup_project_and_session):
        """Test that maybe_ready with repo URL returns True."""
        project_id, _ = setup_project_and_session
        self._add_repo_url(project_id)

        session = get_session()
        try:
            discovery_session = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            discovery_session.readiness_status = "maybe_ready"
            session.commit()
        finally:
            session.close()

        assert ArchitectureTriggerService.is_eligible(project_id) is True
