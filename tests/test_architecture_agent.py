"""Tests for in-house architecture agent (no external webhook)."""
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from app.services.architecture_agent_service import (
    ArchitectureAgentService,
    _normalize_payload,
    _heuristic_generate,
)
from app.db import (
    get_session,
    ProjectModel,
    DiscoverySessionModel,
    ChecklistItemModel,
    ArchitectureResultModel,
)
from app.repositories.architecture_result_repo import ArchitectureResultRepository


def _minimal_context(project_id: str, repo_url: str = "https://github.com/example/repo") -> dict:
    return {
        "project_id": project_id,
        "project_name": "Test Project",
        "repo_url": repo_url,
        "overview": {"summary": "A test app"},
        "stack": {"languages": ["Python"], "frameworks": ["FastAPI"]},
        "components": [{"name": "api", "type": "service"}],
    }


@pytest.fixture
def project_and_session():
    """Create project and discovery session eligible for architecture."""
    session = get_session()
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    try:
        session.add(ProjectModel(
            id=project_id,
            name="Test",
            status="collecting_initial_context",
        ))
        session.add(DiscoverySessionModel(
            id=session_id,
            project_id=project_id,
            state="collecting_initial_context",
            readiness_status="ready_for_architecture",
            started_at=now,
            updated_at=now,
            eligible_for_architecture=False,
            architecture_triggered=False,
        ))
        session.add(ChecklistItemModel(
            id=str(uuid.uuid4()),
            project_id=project_id,
            key="repo_exists",
            label="Repo",
            status="confirmed",
            priority="high",
            value="https://github.com/example/repo",
            updated_at=now,
        ))
        session.commit()
        yield project_id
    finally:
        session.query(ChecklistItemModel).filter(ChecklistItemModel.project_id == project_id).delete()
        session.query(ArchitectureResultModel).filter(ArchitectureResultModel.project_id == project_id).delete()
        session.query(DiscoverySessionModel).filter(DiscoverySessionModel.project_id == project_id).delete()
        session.query(ProjectModel).filter(ProjectModel.id == project_id).delete()
        session.commit()
        session.close()


# --- Scenario 1: Successful internal architecture generation ---

@patch("app.repositories.architecture_result_repo.get_storage_adapter")
@patch("app.services.architecture_agent_service.get_consolidated_context")
def test_architecture_agent_success_returns_expected_shape_and_persists(
    mock_get_context,
    mock_storage,
    project_and_session,
):
    """Scenario 1 — project has valid context; agent runs; returns expected JSON; result persisted."""
    project_id = project_and_session
    mock_get_context.return_value = _minimal_context(project_id)
    mock_storage.return_value = MagicMock()
    mock_storage.return_value.store.return_value = "r2://bucket/test/arch.json"

    result = ArchitectureAgentService.generate(project_id)

    assert result["success"] is True
    payload = result["payload"]
    assert "analise_entrada" in payload
    assert "vibe_economica" in payload
    assert "vibe_performance" in payload
    assert "descricao" in payload["vibe_economica"]
    assert "custo_estimado" in payload["vibe_economica"]
    assert "recursos" in payload["vibe_economica"]
    assert "descricao" in payload["vibe_performance"]
    assert "recursos" in payload["vibe_performance"]

    # Persisted
    session = get_session()
    try:
        arch = ArchitectureResultRepository().get_latest(project_id)
        assert arch is not None
        assert arch.project_id == project_id
    finally:
        session.close()

    ds = get_session().query(DiscoverySessionModel).filter(
        DiscoverySessionModel.project_id == project_id
    ).first()
    get_session().close()
    assert ds.architecture_triggered is True
    assert ds.architecture_trigger_status == "success"
    assert ds.architecture_trigger_target == "internal"


# --- Scenario 2: Readiness guard ---

def test_architecture_agent_not_ready_rejected(project_and_session):
    """Scenario 2 — project not ready; architecture generation rejected cleanly."""
    project_id = project_and_session
    session = get_session()
    try:
        ds = session.query(DiscoverySessionModel).filter(
            DiscoverySessionModel.project_id == project_id
        ).first()
        ds.readiness_status = "not_ready"
        session.commit()
    finally:
        session.close()

    result = ArchitectureAgentService.generate(project_id)
    assert result["success"] is False
    assert "not eligible" in result.get("error", "").lower() or "not ready" in result.get("error", "").lower()


@patch("app.services.architecture_agent_service.get_consolidated_context")
def test_architecture_agent_no_repo_rejected(mock_get_context, project_and_session):
    """Scenario 2 — no repo URL; rejected."""
    project_id = project_and_session
    session = get_session()
    try:
        session.query(ChecklistItemModel).filter(
            ChecklistItemModel.project_id == project_id,
            ChecklistItemModel.key == "repo_exists",
        ).delete()
        session.commit()
    finally:
        session.close()

    result = ArchitectureAgentService.generate(project_id)
    assert result["success"] is False


# --- Scenario 3: Missing context artifact (rebuilt from DB) ---

@patch("app.repositories.architecture_result_repo.get_storage_adapter")
@patch("app.services.architecture_agent_service.get_consolidated_context")
def test_architecture_agent_rebuilt_context_still_generates(mock_get_context, mock_storage, project_and_session):
    """Scenario 3 — saved artifact missing; context is minimal (rebuilt from DB); generation still works."""
    project_id = project_and_session
    # Minimal context as if rebuilt from DB (no storage file)
    mock_get_context.return_value = {
        "project_id": project_id,
        "project_name": "Unknown",
        "repo_url": "https://github.com/example/repo",
        "analysis_status": "no_context_available",
    }
    mock_storage.return_value = MagicMock()
    mock_storage.return_value.store.return_value = "r2://bucket/arch.json"

    result = ArchitectureAgentService.generate(project_id)

    assert result["success"] is True
    assert result["payload"]["analise_entrada"]
    assert result["payload"]["vibe_economica"]["descricao"]
    assert result["payload"]["vibe_performance"]["descricao"]


# --- Scenario 4: Old webhook path removed ---

@patch("requests.post")
@patch("app.repositories.architecture_result_repo.get_storage_adapter")
@patch("app.services.architecture_agent_service.get_consolidated_context")
def test_architecture_flow_does_not_call_webhook(mock_get_context, mock_storage, mock_requests_post, project_and_session):
    """Scenario 4 — architecture flow does not send requests to any webhook URL."""
    project_id = project_and_session
    mock_get_context.return_value = _minimal_context(project_id)
    mock_storage.return_value = MagicMock()
    mock_storage.return_value.store.return_value = "r2://bucket/arch.json"

    ArchitectureAgentService.generate(project_id)

    mock_requests_post.assert_not_called()


# --- Scenario 5: Malformed model output ---

def test_normalize_payload_handles_malformed_vibes():
    """Scenario 5 — malformed vibe shape is normalized; no crash."""
    raw = {
        "analise_entrada": "ok",
        "vibe_economica": None,
        "vibe_performance": {"description": "x", "estimated_cost": "y", "resources": []},
    }
    out = _normalize_payload(raw)
    assert out["analise_entrada"] == "ok"
    assert out["vibe_economica"]["descricao"] == ""
    assert out["vibe_economica"]["recursos"] == []
    assert out["vibe_performance"]["descricao"] == "x"
    assert out["vibe_performance"]["custo_estimado"] == "y"


def test_heuristic_generate_always_returns_valid_contract():
    """Heuristic generator returns the expected contract shape."""
    ctx = {"project_id": "p1", "project_name": "P", "repo_url": "https://x"}
    out = _heuristic_generate(ctx)
    assert "analise_entrada" in out
    assert "vibe_economica" in out
    assert "vibe_performance" in out
    assert "descricao" in out["vibe_economica"]
    assert "recursos" in out["vibe_economica"]
    assert isinstance(out["vibe_economica"]["recursos"], list)
