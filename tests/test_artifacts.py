import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def project_id():
    resp = client.post("/projects", json={"project_name": "Demo", "summary": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "project_id" in data
    return data["project_id"]


def test_markdown_skeletons_present(project_id):
    filenames = [
        "01-overview.md",
        "02-stack.md",
        "03-components.md",
        "04-dependencies.md",
        "05-flows.md",
        "06-assumptions.md",
        "07-open-questions.md",
    ]
    for fname in filenames:
        resp = client.get(f"/projects/{project_id}/markdown/{fname}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("filename") == fname
        assert "content" in data


def test_graph_skeletons_empty(project_id):
    # System graph JSON
    resp = client.get(f"/projects/{project_id}/graphs/system_graph.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("filename") == "system_graph.json"
    assert isinstance(data.get("content"), dict)
    assert "nodes" in data["content"]

    # Flow graph JSON
    resp = client.get(f"/projects/{project_id}/graphs/flow_graph.json")
    assert resp.status_code == 200

    # Deployment hints
    resp = client.get(f"/projects/{project_id}/graphs/deployment_hints.json")
    assert resp.status_code == 200

    # System graph DSL
    resp = client.get(f"/projects/{project_id}/graphs/system_graph.dsl")
    assert resp.status_code == 200
    assert isinstance(resp.json().get("content"), str)

    # Flow graph DSL
    resp = client.get(f"/projects/{project_id}/graphs/flow_graph.dsl")
    assert resp.status_code == 200
