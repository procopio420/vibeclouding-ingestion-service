"""Tests for repo panel, project.repo.updated event, and manual architecture start."""
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import discovery as discovery_routes
from app.api.routes import architecture as architecture_routes
from app.api.routes import projects as projects_routes
from app.db import (
    get_session,
    ProjectModel,
    DiscoverySessionModel,
    ChecklistItemModel,
    ArchitectureResultModel,
)
from app.websocket.assistant_runner import AssistantRunner
from app.websocket.schemas import ServerEventType
from app.discovery.chat_service import ChatService
from app.services.context_aggregator import REPO_ABSENT_VALUE


def _test_app():
    """Minimal app with only discovery, architecture, and projects routes (no Celery)."""
    app = FastAPI()
    app.include_router(projects_routes.router)
    app.include_router(discovery_routes.router)
    app.include_router(architecture_routes.router)
    return app


client = TestClient(_test_app())


def _make_project_and_session(project_id=None, session_id=None, readiness="not_ready", repo_url=None):
    """Create project, discovery session, and optionally repo_exists checklist item."""
    project_id = project_id or str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())
    now = datetime.utcnow()
    session = get_session()
    try:
        project = ProjectModel(
            id=project_id,
            name="Test",
            status="collecting_initial_context",
        )
        session.add(project)
        discovery_session = DiscoverySessionModel(
            id=session_id,
            project_id=project_id,
            state="collecting_initial_context",
            readiness_status=readiness,
            started_at=now,
            updated_at=now,
            eligible_for_architecture=False,
            architecture_triggered=False,
        )
        session.add(discovery_session)
        if repo_url is not None:
            item = ChecklistItemModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                key="repo_exists",
                label="Repo",
                status="confirmed" if repo_url and repo_url != REPO_ABSENT_VALUE else "missing",
                priority="high",
                value=repo_url or None,
                updated_at=now,
            )
            session.add(item)
        session.commit()
        return project_id, session_id
    finally:
        session.close()


def _teardown(project_id):
    session = get_session()
    try:
        session.query(ChecklistItemModel).filter(ChecklistItemModel.project_id == project_id).delete()
        session.query(ArchitectureResultModel).filter(ArchitectureResultModel.project_id == project_id).delete()
        session.query(DiscoverySessionModel).filter(DiscoverySessionModel.project_id == project_id).delete()
        session.query(ProjectModel).filter(ProjectModel.id == project_id).delete()
        session.commit()
    finally:
        session.close()


class TestRepoPanelEndpoint:
    """Scenario 2 — repo missing; Scenario 3 — maybe_ready with repo."""

    def test_panel_repo_missing_can_start_false(self):
        """Repo missing: repo_panel missing, can_start_architecture false."""
        project_id, _ = _make_project_and_session(repo_url=None)
        try:
            resp = client.get(f"/projects/{project_id}/discovery/panel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repo_panel"]["has_repo_url"] is False
            assert data["repo_panel"]["repo_url"] is None
            assert data["repo_panel"]["repo_status"] == "missing"
            assert data["can_start_architecture"] is False
            assert data["architecture_panel"]["can_start_architecture"] is False
        finally:
            _teardown(project_id)

    def test_panel_maybe_ready_with_repo_can_start_true(self):
        """maybe_ready with repo: can_start_architecture true."""
        project_id, _ = _make_project_and_session(
            readiness="maybe_ready",
            repo_url="https://github.com/example/repo",
        )
        try:
            resp = client.get(f"/projects/{project_id}/discovery/panel")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repo_panel"]["has_repo_url"] is True
            assert data["repo_panel"]["repo_url"] == "https://github.com/example/repo"
            assert data["repo_panel"]["repo_status"] == "linked"
            assert data["can_start_architecture"] is True
            assert data["architecture_panel"]["architecture_status"] == "not_started"
            assert data["architecture_panel"]["architecture_triggered"] is False
        finally:
            _teardown(project_id)

    def test_panel_404_when_project_missing(self):
        resp = client.get("/projects/nonexistent-id/discovery/panel")
        assert resp.status_code == 404


class TestRepoUrlDetectionAndWebSocket:
    """Scenario 1 — user sends repo URL in chat: detected, persisted, event emitted."""

    def test_chat_service_detect_and_normalize(self):
        """detect_repo_url returns normalized https URL."""
        svc = ChatService()
        assert svc.detect_repo_url("Check out https://github.com/user/repo") == "https://github.com/user/repo"
        assert svc.detect_repo_url("My repo is git@github.com:user/project.git") == "https://github.com/user/project"
        assert svc.detect_repo_url("I don't have a repo yet") is None

    def test_assistant_runner_emits_project_repo_updated_when_repo_detected(self):
        """When orchestrator returns repo_url_detected, stream includes project.repo.updated."""
        project_id, session_id = _make_project_and_session(repo_url=None)
        try:
            # Simulate orchestrator returning with repo_url_detected
            class FakeOrchestrator:
                def handle_user_message(self, pid, msg):
                    return {
                        "assistant_message": {"id": "m1", "content": "Got it."},
                        "user_message": {"id": "u1"},
                        "checklist": [],
                        "readiness": {},
                        "repo_url_detected": "https://github.com/acme/app",
                        "state_transition": None,
                        "questions_created": [],
                    }

            runner = AssistantRunner()
            events = []
            import asyncio
            async def collect():
                async for ev in runner.run(
                    project_id=project_id,
                    user_message="https://github.com/acme/app",
                    run_id="r1",
                    orchestrator=FakeOrchestrator(),
                ):
                    events.append(ev.to_dict())

            asyncio.run(collect())

            repo_events = [e for e in events if e.get("type") == ServerEventType.PROJECT_REPO_UPDATED.value]
            assert len(repo_events) == 1
            assert repo_events[0]["data"]["project_id"] == project_id
            assert repo_events[0]["data"]["repo_url"] == "https://github.com/acme/app"
            assert repo_events[0]["data"]["has_repo_url"] is True
        finally:
            _teardown(project_id)


class TestStartArchitectureEndpoint:
    """Manual start runs internal agent and persists; duplicate prevented; no webhook."""

    @patch("app.repositories.architecture_result_repo.get_storage_adapter")
    @patch("app.services.architecture_agent_service.get_consolidated_context")
    def test_post_start_architecture_runs_internal_agent_and_persists(self, mock_get_context, mock_storage):
        """POST start-architecture runs internal agent, persists result, no webhook."""
        project_id, _ = _make_project_and_session(
            readiness="maybe_ready",
            repo_url="https://github.com/example/repo",
        )
        try:
            mock_get_context.return_value = {
                "project_id": project_id,
                "project_name": "Test",
                "repo_url": "https://github.com/example/repo",
                "overview": {},
                "stack": {},
                "components": [],
            }
            mock_storage.return_value = MagicMock()
            mock_storage.return_value.store.return_value = "r2://bucket/arch.json"

            resp = client.post(f"/projects/{project_id}/start-architecture")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "message" in data

            session = get_session()
            try:
                ds = session.query(DiscoverySessionModel).filter(
                    DiscoverySessionModel.project_id == project_id
                ).first()
                assert ds.architecture_triggered is True
                assert ds.architecture_triggered_at is not None
                assert ds.architecture_trigger_status == "success"
                assert ds.architecture_started_by == "manual_button"
            finally:
                session.close()

            get_resp = client.get(f"/projects/{project_id}/architecture-result")
            assert get_resp.status_code == 200
            result = get_resp.json()
            assert "analise_entrada" in result
            assert "vibe_economica" in result
            assert "vibe_performance" in result
        finally:
            _teardown(project_id)

    def test_post_start_architecture_already_triggered_returns_400(self):
        """Already triggered: 400, no duplicate run."""
        project_id, _ = _make_project_and_session(
            readiness="ready_for_architecture",
            repo_url="https://github.com/example/repo",
        )
        session = get_session()
        try:
            ds = session.query(DiscoverySessionModel).filter(
                DiscoverySessionModel.project_id == project_id
            ).first()
            ds.architecture_triggered = True
            ds.architecture_triggered_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

        try:
            resp = client.post(f"/projects/{project_id}/start-architecture")
            assert resp.status_code == 400
        finally:
            _teardown(project_id)

    def test_post_start_architecture_no_repo_returns_400(self):
        """No repo URL: 400."""
        project_id, _ = _make_project_and_session(readiness="ready_for_architecture", repo_url=None)
        try:
            resp = client.post(f"/projects/{project_id}/start-architecture")
            assert resp.status_code == 400
        finally:
            _teardown(project_id)

    def test_post_start_architecture_404_when_no_session(self):
        """No discovery session: 404."""
        project_id = str(uuid.uuid4())
        session = get_session()
        try:
            session.add(ProjectModel(
                id=project_id,
                name="NoSession",
                status="created",
            ))
            session.commit()
        finally:
            session.close()
        try:
            resp = client.post(f"/projects/{project_id}/start-architecture")
            assert resp.status_code == 404
        finally:
            _teardown(project_id)

    def test_post_start_architecture_already_has_result_returns_400(self):
        """Architecture result already exists: 400."""
        project_id, _ = _make_project_and_session(
            readiness="ready_for_architecture",
            repo_url="https://github.com/example/repo",
        )
        session = get_session()
        try:
            session.add(ArchitectureResultModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                schema_version="1.0",
                is_latest="true",
                raw_payload="{}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ))
            session.commit()
        finally:
            session.close()

        try:
            resp = client.post(f"/projects/{project_id}/start-architecture")
            assert resp.status_code == 400
        finally:
            _teardown(project_id)
