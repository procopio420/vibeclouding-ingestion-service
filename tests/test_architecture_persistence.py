import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def project_id():
    resp = client.post("/projects", json={"project_name": "Test Arch", "summary": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "project_id" in data
    return data["project_id"]


@pytest.fixture
def sample_architecture_payload():
    return {
        "analise_entrada": {
            "contexto": {
                "project_type": "webapp",
                "stack": ["Python", "FastAPI", "PostgreSQL"]
            },
            "requisitos": [
                {"tipo": "funcional", "descricao": "API REST"},
                {"tipo": "nao_funcional", "descricao": "Alta disponibilidade"}
            ]
        },
        "vibe_economica": {
            "descricao": "Arquitetura serverless com pay-per-use",
            "custo_estimado": "USD 50-100/month",
            "recursos": [
                {
                    "servico": "AWS Lambda",
                    "config": {"memory": 512, "timeout": 30}
                },
                {
                    "servico": "AWS RDS PostgreSQL",
                    "config": {"instance": "db.t3.micro"}
                }
            ]
        },
        "vibe_performance": {
            "descricao": "Baixa latencia com cache em memoria",
            "custo_estimado": "P95 < 200ms",
            "recursos": [
                {
                    "servico": "CloudFront",
                    "config": {"price_class": "PriceClass_100"}
                },
                {
                    "servico": "ElastiCache",
                    "config": {"node_type": "cache.t2.micro"}
                }
            ]
        }
    }


@patch('app.repositories.architecture_result_repo.get_storage_adapter')
def test_architecture_result_saved_to_db_and_storage(mock_storage, project_id, sample_architecture_payload):
    mock_storage_instance = MagicMock()
    mock_storage_instance.store.return_value = "r2://bucket/test/architecture/architecture_result.json"
    mock_storage.return_value = mock_storage_instance
    
    resp = client.post(
        f"/projects/{project_id}/architecture-result",
        json=sample_architecture_payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    
    assert "architecture_result_id" in data
    assert data["project_id"] == project_id
    assert data["schema_version"] == "1.0"
    assert data["status"] == "saved"
    assert "raw_payload_storage_key" in data
    
    assert data["analise_entrada"]["contexto"]["project_type"] == "webapp"
    assert data["vibe_economica"]["descricao"] == "Arquitetura serverless com pay-per-use"
    assert data["vibe_performance"]["descricao"] == "Baixa latencia com cache em memoria"
    
    mock_storage_instance.store.assert_called_once()


@patch('app.repositories.architecture_result_repo.get_storage_adapter')
def test_get_returns_latest_architecture(mock_storage, project_id, sample_architecture_payload):
    mock_storage_instance = MagicMock()
    mock_storage_instance.store.return_value = "r2://bucket/test/architecture/architecture_result.json"
    mock_storage.return_value = mock_storage_instance
    
    create_resp = client.post(
        f"/projects/{project_id}/architecture-result",
        json=sample_architecture_payload
    )
    assert create_resp.status_code == 200
    
    get_resp = client.get(f"/projects/{project_id}/architecture-result")
    assert get_resp.status_code == 200
    data = get_resp.json()
    
    assert data["project_id"] == project_id
    assert "architecture_result_id" in data


def test_404_when_no_architecture(project_id):
    resp = client.get(f"/projects/{project_id}/architecture-result")
    assert resp.status_code == 404


def test_404_for_nonexistent_project():
    resp = client.get("/projects/nonexistent-project-id/architecture-result")
    assert resp.status_code == 404


@patch('app.repositories.architecture_result_repo.get_storage_adapter')
def test_storage_upload_failure_handled(mock_storage, project_id, sample_architecture_payload):
    mock_storage_instance = MagicMock()
    mock_storage_instance.store.side_effect = Exception("S3 connection failed")
    mock_storage.return_value = mock_storage_instance
    
    resp = client.post(
        f"/projects/{project_id}/architecture-result",
        json=sample_architecture_payload
    )
    
    assert resp.status_code == 500
    assert "Failed to save architecture result" in resp.json()["detail"]


def test_invalid_json_body_not_object(project_id):
    resp = client.post(
        f"/projects/{project_id}/architecture-result",
        json=[1, 2, 3]
    )
    assert resp.status_code == 422
    assert "must be a JSON object" in resp.json()["detail"]


def test_architecture_with_extra_fields(project_id):
    mock_storage_instance = MagicMock()
    mock_storage_instance.store.return_value = "r2://bucket/test/architecture/architecture_result.json"
    
    with patch('app.repositories.architecture_result_repo.get_storage_adapter', return_value=mock_storage_instance):
        payload_with_extra = {
            "analise_entrada": {"contexto": {"project_type": "api"}},
            "vibe_economica": {"descricao": "cost-effective"},
            "vibe_performance": {"descricao": "fast"},
            "extra_field": "should be preserved in raw_payload",
            "another_extra": {"nested": "value"}
        }
        
        resp = client.post(f"/projects/{project_id}/architecture-result", json=payload_with_extra)
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["analise_entrada"]["contexto"]["project_type"] == "api"
        assert data["vibe_economica"]["descricao"] == "cost-effective"
        assert data["vibe_performance"]["descricao"] == "fast"
