from app.domain.models import ProjectContext


def test_project_context_defaults():
    pc = ProjectContext(project_name="Demo")
    assert pc.version == 1
    assert pc.project_name == "Demo"
