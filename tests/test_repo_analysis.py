"""Tests for repo analysis pipeline."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from app.repo_analysis.file_parsers import (
    parse_docker_compose,
    parse_dockerfile,
    parse_env_example,
    parse_makefile,
    parse_package_json,
    parse_pyproject_toml,
    parse_requirements_txt,
    parse_readme,
)
from app.repo_analysis.repo_adapter import parse_repo, analyze_repo
from app.repo_analysis.signals_model import ExtractedSignals
from app.repo_analysis.llm_enrichment import NoOpAnalyzer, get_llm_analyzer
from app.serializers.markdown_serializer import render_all
from app.serializers.graph_json_serializer import (
    serialize_system_graph,
    serialize_flow_graph,
    serialize_deployment_hints,
)
from app.serializers.graph_dsl_serializer import (
    serialize_system_graph_dsl,
    serialize_flow_graph_dsl,
)


class TestFileParsers:
    """Test file parsers."""
    
    def test_parse_requirements_txt(self):
        content = """fastapi==0.110.0
Flask>=2.0
django
redis
pytest
"""
        result = parse_requirements_txt(content)
        dep_names = [d["name"] for d in result["dependencies"]]
        assert "fastapi" in dep_names
        assert "Flask" in result["frameworks"]
        assert "Django" in result["frameworks"]
        assert "Redis" in result["databases"]
        # Check role classification
        roles = {d["name"]: d["role"] for d in result["dependencies"]}
        assert roles.get("fastapi") == "api_framework"
        assert roles.get("redis") == "cache_broker"
        assert roles.get("pytest") == "testing"
    
    def test_parse_pyproject_toml(self):
        content = """
[project]
name = "test-project"
description = "A test project"

dependencies = [
    "fastapi",
    "sqlalchemy",
]

[project.optional-dependencies]
dev = ["pytest"]

[build-system]
requires = ["setuptools"]
"""
        result = parse_pyproject_toml(content)
        assert result["project_name"] == "test-project"
        dep_names = [d["name"] for d in result["dependencies"]]
        assert "fastapi" in dep_names
        assert "FastAPI" in result["frameworks"]
        # Check role classification
        roles = {d["name"]: d["role"] for d in result["dependencies"]}
        assert roles.get("fastapi") == "api_framework"
        assert roles.get("sqlalchemy") == "orm"
    
    def test_parse_package_json(self):
        content = json.dumps({
            "name": "my-app",
            "description": "A test app",
            "dependencies": {
                "express": "^4.0.0",
                "react": "^18.0.0"
            },
            "devDependencies": {
                "vite": "^5.0.0"
            }
        })
        result = parse_package_json(content)
        assert result["project_name"] == "my-app"
        dep_names = [d["name"] for d in result["dependencies"]]
        assert "express" in dep_names
        assert "React" in result["frameworks"]
        assert "Vite" in result["frameworks"]
        # Check role classification
        roles = {d["name"]: d["role"] for d in result["dependencies"]}
        assert roles.get("express") == "api_framework"
    
    def test_parse_docker_compose(self):
        content = """
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://db
  db:
    image: postgres:15
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis:
    image: redis:7
volumes:
  pgdata:
"""
        result = parse_docker_compose(content)
        assert "api" in result["services"]
        assert "db" in result["services"]
        assert "redis" in result["services"]
    
    def test_parse_dockerfile(self):
        content = """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
"""
        result = parse_dockerfile(content)
        assert "python:3.11-slim" in result["base_image"]
        assert "8000" in result["exposed_ports"]
        assert "WORKDIR" in result["commands"]
    
    def test_parse_env_example(self):
        content = """# Database config
DATABASE_URL=postgres://user:pass@localhost/db
POSTGRES_HOST=localhost
# Redis config
REDIS_URL=redis://localhost:6379
# Auth
JWT_SECRET=changeme
"""
        result = parse_env_example(content)
        assert "DATABASE_URL" in result["env_vars"]
        assert "database" in result["inferred_categories"]
        assert "redis" in result["inferred_categories"]
    
    def test_parse_makefile(self):
        content = """
.PHONY: test run build

run:
\tpython main.py

test:
\tpytest tests/

build:
\tdocker build .
"""
        result = parse_makefile(content)
        assert "run" in result["targets"]
        assert "test" in result["targets"]
        assert "build" in result["targets"]
        assert "test" in result["inferred_commands"]
    
    def test_parse_readme(self):
        content = """# My Project

This is a test project.

## Installation

Run `pip install` to install.

## Usage

```python
print("hello")
```
"""
        result = parse_readme(content)
        assert result["title"] == "My Project"
        assert "Installation" in result["sections"]
        assert result["has_code_examples"] is True


class TestRepoAdapter:
    """Test repo adapter."""
    
    def test_parse_repo_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            (repo_path / "README.md").write_text("# Test Project\nA test repo.")
            (repo_path / "requirements.txt").write_text("fastapi\nredis\nsqlalchemy\n")
            (repo_path / "Dockerfile").write_text("FROM python:3.11\n")
            (repo_path / ".env.example").write_text("DATABASE_URL=test\n")
            
            signals = parse_repo(str(repo_path), "local")
            
            assert "Python" in [l.name for l in signals.languages]
            assert len(signals.frameworks) > 0
            assert len(signals.components) > 0
    
    def test_parse_repo_with_pyproject(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            (repo_path / "README.md").write_text("# API Project\n")
            (repo_path / "pyproject.toml").write_text("""
[project]
name = "my-api"
dependencies = ["fastapi", "pydantic"]

[project.optional-dependencies]
dev = ["pytest"]
""")
            (repo_path / "src").mkdir()
            (repo_path / "src" / "main.py").write_text("# main")
            
            signals = parse_repo(str(repo_path), "local")
            
            assert signals.project_name == "my-api"
            assert "FastAPI" in [f.name for f in signals.frameworks]
    
    def test_parse_repo_with_package_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            (repo_path / "package.json").write_text(json.dumps({
                "name": "frontend-app",
                "dependencies": {"react": "^18"}
            }))
            (repo_path / "src").mkdir()
            
            signals = parse_repo(str(repo_path), "local")
            
            assert signals.project_name == "frontend-app"
            assert "JavaScript/TypeScript" in [l.name for l in signals.languages]
            assert "React" in [f.name for f in signals.frameworks]
    
    def test_parse_repo_with_docker_compose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            (repo_path / "docker-compose.yml").write_text("""
services:
  api:
    build: .
  db:
    image: postgres:15
  redis:
    image: redis:7
""")
            
            signals = parse_repo(str(repo_path), "local")
            
            infra_names = [i.name for i in signals.infrastructure]
            assert "Docker Compose" in infra_names
    
    def test_analyze_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            
            (repo_path / "README.md").write_text("# Test\nA test project.")
            (repo_path / "requirements.txt").write_text("fastapi\n")
            (repo_path / "api").mkdir()
            (repo_path / "worker").mkdir()
            
            context = analyze_repo(str(repo_path), "local")
            
            assert len(context.get("components", [])) > 0


class TestLLMEnrichment:
    """Test LLM enrichment."""
    
    def test_noop_analyzer(self):
        analyzer = NoOpAnalyzer()
        assert analyzer.is_available() is True
        
        signals = ExtractedSignals(
            project_name="test",
            project_type="api",
            summary="test",
            source_metadata={"source_type": "repo", "extraction_method": "heuristics"},
        )
        
        result = analyzer.analyze(signals)
        assert result.project_name == "test"
    
    def test_get_llm_analyzer_default(self):
        analyzer = get_llm_analyzer()
        assert isinstance(analyzer, NoOpAnalyzer)


class TestSerializers:
    """Test serializers produce real content."""
    
    def test_markdown_serializer(self):
        context = {
            "project_name": "Test Project",
            "project_type": "api",
            "summary": "A test API project.",
            "stack": {
                "languages": ["Python"],
                "frameworks": ["FastAPI", "SQLAlchemy"],
                "databases": ["PostgreSQL"],
                "infrastructure": ["Docker"],
                "external_services": [],
            },
            "components": [
                {"name": "api", "type": "backend", "description": "Main API", "tech": ["FastAPI"]},
                {"name": "worker", "type": "worker", "description": "Background worker", "tech": ["Celery"]},
            ],
            "flows": [
                {"name": "api_to_db", "source": "api", "target": "database", "flow_type": "data", "confidence": 0.7},
            ],
            "dependencies": [
                {"name": "fastapi", "type": "python-package", "role": "runtime", "confidence": 0.9},
            ],
            "assumptions": ["Uses SQLAlchemy ORM"],
            "open_questions": ["What is the deployment target?"],
            "uncertainties": [],
        }
        
        artifacts = render_all(context)
        
        assert "01-overview.md" in artifacts
        assert "Test Project" in artifacts["01-overview.md"]
        assert "FastAPI" in artifacts["02-stack.md"]
        assert "api" in artifacts["03-components.md"]
    
    def test_graph_json_serializer(self):
        context = {
            "components": [
                {"name": "api", "type": "backend", "description": "API", "tech": []},
                {"name": "worker", "type": "worker", "description": "Worker", "tech": []},
            ],
            "flows": [
                {"source": "api", "target": "worker", "flow_type": "message", "confidence": 0.8},
            ],
            "stack": {
                "infrastructure": ["Docker"],
                "databases": ["PostgreSQL"],
            },
            "assumptions": [],
            "open_questions": [],
            "uncertainties": [],
        }
        
        system = serialize_system_graph(context)
        assert len(system["nodes"]) > 0
        
        flow = serialize_flow_graph(context)
        assert len(flow["flows"]) > 0
        
        deployment = serialize_deployment_hints(context)
        assert "likely_public_services" in deployment
    
    def test_graph_dsl_serializer(self):
        context = {
            "components": [
                {"name": "api", "type": "backend", "description": "API", "tech": ["FastAPI"]},
                {"name": "worker", "type": "worker", "description": "Worker", "tech": ["Celery"]},
            ],
            "flows": [
                {"source": "api", "target": "worker", "flow_type": "message", "confidence": 0.8},
            ],
            "stack": {"infrastructure": []},
        }
        
        system_dsl = serialize_system_graph_dsl(context)
        assert "api" in system_dsl
        
        flow_dsl = serialize_flow_graph_dsl(context)
        assert "api" in flow_dsl
