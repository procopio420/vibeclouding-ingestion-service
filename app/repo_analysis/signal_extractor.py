"""Signal extraction from repository structure and parsed files."""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.repo_analysis.file_parsers import (
    parse_docker_compose,
    parse_dockerfile,
    parse_env_example,
    parse_makefile,
    parse_package_json,
    parse_pyproject_toml,
    parse_readme,
    parse_requirements_txt,
    read_file_safe,
)


COMMON_DIR_PATTERNS = {
    "frontend": ["frontend", "client", "web", "ui", "app"],
    "backend": ["backend", "server", "api", "service"],
    "worker": ["worker", "jobs", "tasks", "celery", "scheduler"],
    "database": ["db", "database", "migrations", "alembic"],
    "config": ["config", "configs", "configuration"],
    "docs": ["docs", "documentation"],
    "tests": ["tests", "test", "__tests__", "specs", "e2e"],
    "scripts": ["scripts", "tools", "bin", "scripts"],
    "infra": ["infra", "infrastructure", "terraform", "cloudformation", "kubernetes", "k8s"],
    "docker": ["docker"],
    "models": ["models", "schemas", "entities"],
    "services": ["services", "lib", "core"],
    "utils": ["utils", "helpers", "common"],
    "middleware": ["middleware"],
    "routes": ["routes", "endpoints", "controllers"],
}

FRAMEWORK_DIR_PATTERNS = {
    "FastAPI": ["api", "routes", "endpoints"],
    "Django": ["apps", "management", "migrations"],
    "Express": ["routes", "controllers"],
    "React": ["components", "pages", "hooks", "context"],
    "Next.js": ["pages", "components", "app", "public"],
}

SERVICE_INDICATORS = {
    "postgres": ["postgres", "postgresql", "db"],
    "mysql": ["mysql", "mariadb"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis", "cache"],
    "elasticsearch": ["elasticsearch", "es"],
    "rabbitmq": ["rabbitmq", "amqp", "queue"],
    "nginx": ["nginx", "reverse-proxy"],
    "minio": ["minio", "s3"],
}


def get_top_level_structure(repo_path: str) -> Dict[str, Any]:
    """Get top-level directory structure."""
    root = Path(repo_path)
    dirs = []
    files = []
    
    try:
        for entry in root.iterdir():
            if entry.is_dir():
                if not entry.name.startswith(".") and entry.name not in ["node_modules", "__pycache__", "venv", ".git"]:
                    dirs.append(entry.name)
            else:
                if not entry.name.startswith("."):
                    files.append(entry.name)
    except Exception:
        pass
    
    return {"directories": sorted(dirs), "files": sorted(files)}


def infer_project_type(structure: Dict, parsed_files: Dict) -> str:
    """Infer project type from structure and parsed files."""
    dirs = structure.get("directories", [])
    files = structure.get("files", [])
    
    has_py = any(f in ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"] for f in files)
    has_js = "package.json" in files
    has_docker = "Dockerfile" in files or "docker-compose.yml" in files or "docker-compose.yaml" in files
    
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    js_parsed = parsed_files.get("package")
    
    py_frameworks = py_parsed.get("frameworks", []) if py_parsed else []
    js_frameworks = js_parsed.get("frameworks", []) if js_parsed else []
    
    has_frontend = any(d in dirs for d in ["frontend", "client", "web", "ui"])
    has_backend = any(d in dirs for d in ["backend", "server", "api"])
    has_worker = any(d in dirs for d in ["worker", "jobs", "tasks"])
    
    if has_py and has_js:
        return "fullstack"
    elif has_py and has_frontend:
        return "fullstack"
    elif has_py and has_backend and has_frontend:
        return "fullstack"
    elif has_py:
        if "FastAPI" in py_frameworks or "Flask" in py_frameworks:
            return "python-api"
        elif "Django" in py_frameworks:
            return "django"
        elif "Celery" in py_frameworks:
            return "python-worker"
        return "python"
    elif has_js:
        if "React" in js_frameworks or "Vue" in js_frameworks or "Next.js" in js_frameworks:
            return "frontend"
        elif "Express" in js_frameworks or "Fastify" in js_frameworks:
            return "node-api"
        return "javascript"
    elif has_docker:
        return "dockerized"
    else:
        return "unknown"


def detect_components(structure: Dict, parsed_files: Dict) -> List[Dict[str, Any]]:
    """Detect components from structure and parsed files."""
    components = []
    dirs = structure.get("directories", [])
    files = structure.get("files", [])
    
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    js_parsed = parsed_files.get("package")
    compose_parsed = parsed_files.get("docker_compose")
    
    has_frontend = any(d in dirs for d in ["frontend", "client", "web", "ui"])
    has_backend = any(d in dirs for d in ["backend", "server", "api"])
    has_worker = any(d in dirs for d in ["worker", "jobs", "tasks"])
    has_db = any(d in dirs for d in ["db", "database", "migrations"])
    
    py_frameworks = py_parsed.get("frameworks", []) if py_parsed else []
    js_frameworks = js_parsed.get("frameworks", []) if js_parsed else []
    
    if has_frontend:
        frontend_frameworks = []
        if "React" in js_frameworks:
            frontend_frameworks.append("React")
        if "Next.js" in js_frameworks:
            frontend_frameworks.append("Next.js")
        if "Vue" in js_frameworks:
            frontend_frameworks.append("Vue.js")
        
        components.append({
            "name": "frontend",
            "type": "frontend",
            "description": "Frontend application",
            "tech": frontend_frameworks or ["JavaScript/TypeScript"],
        })
    
    if has_backend:
        backend_frameworks = []
        if "FastAPI" in py_frameworks:
            backend_frameworks.append("FastAPI")
        if "Flask" in py_frameworks:
            backend_frameworks.append("Flask")
        if "Django" in py_frameworks:
            backend_frameworks.append("Django")
        if "Express" in js_frameworks:
            backend_frameworks.append("Express")
        
        components.append({
            "name": "backend",
            "type": "api",
            "description": "Backend API service",
            "tech": backend_frameworks or ["Python", "Node.js"],
        })
    
    if has_worker:
        worker_frameworks = []
        if "Celery" in py_frameworks:
            worker_frameworks.append("Celery")
        
        components.append({
            "name": "worker",
            "type": "worker",
            "description": "Background worker/processor",
            "tech": worker_frameworks or ["Python"],
        })
    
    if has_db:
        components.append({
            "name": "database",
            "type": "database",
            "description": "Database migrations",
            "tech": ["SQLAlchemy", "Alembic"],
        })
    
    if compose_parsed and compose_parsed.get("services"):
        for svc in compose_parsed["services"]:
            if svc not in [c["name"] for c in components]:
                components.append({
                    "name": svc,
                    "type": "service",
                    "description": f"Docker service: {svc}",
                    "tech": [],
                })
    
    if "redis" in str(compose_parsed.get("services", [])).lower() or "redis" in files:
        components.append({
            "name": "redis",
            "type": "cache",
            "description": "Redis cache service",
            "tech": ["Redis"],
        })
    
    if not components:
        components.append({
            "name": "application",
            "type": "module",
            "description": "Main application",
            "tech": [],
        })
    
    return components


def detect_flows(components: List[Dict], parsed_files: Dict) -> List[Dict[str, Any]]:
    """Detect simple flows between components."""
    flows = []
    component_names = [c["name"] for c in components]
    
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    js_parsed = parsed_files.get("package")
    compose_parsed = parsed_files.get("docker_compose")
    env_parsed = parsed_files.get("env_example")
    
    frontend = next((c for c in components if c["type"] == "frontend"), None)
    backend = next((c for c in components if c["type"] == "api"), None)
    worker = next((c for c in components if c["type"] == "worker"), None)
    
    if frontend and backend:
        flows.append({
            "name": "frontend_to_api",
            "source": frontend["name"],
            "target": backend["name"],
            "description": "Frontend makes API requests to backend",
            "confidence": 0.8,
        })
    
    if backend:
        if py_parsed and "sqlalchemy" in str(py_parsed.get("dependencies", [])).lower():
            flows.append({
                "name": "api_to_database",
                "source": backend["name"],
                "target": "database",
                "description": "Backend queries database",
                "confidence": 0.7,
            })
        
        if py_parsed and "redis" in str(py_parsed.get("dependencies", [])).lower():
            flows.append({
                "name": "api_to_cache",
                "source": backend["name"],
                "target": "redis",
                "description": "Backend uses Redis for caching",
                "confidence": 0.6,
            })
    
    if worker and backend:
        flows.append({
            "name": "worker_to_backend",
            "source": worker["name"],
            "target": backend["name"],
            "description": "Worker processes tasks, may query backend",
            "confidence": 0.5,
        })
    
    if compose_parsed and compose_parsed.get("services"):
        services = compose_parsed["services"]
        
        for svc in services:
            if svc not in component_names:
                continue
            
            if "db" in svc.lower() or "postgres" in svc.lower():
                if backend:
                    flows.append({
                        "name": f"api_to_{svc}",
                        "source": backend["name"],
                        "target": svc,
                        "description": f"Backend connects to {svc}",
                        "confidence": 0.7,
                    })
            
            if "redis" in svc.lower():
                if backend:
                    flows.append({
                        "name": f"api_to_{svc}",
                        "source": backend["name"],
                        "target": svc,
                        "description": f"Backend connects to {svc}",
                        "confidence": 0.6,
                    })
    
    return flows


def detect_dependencies(parsed_files: Dict) -> List[Dict[str, Any]]:
    """Detect external dependencies from parsed files."""
    dependencies = []
    
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    js_parsed = parsed_files.get("package")
    compose_parsed = parsed_files.get("docker_compose")
    env_parsed = parsed_files.get("env_example")
    
    if py_parsed:
        for dep in py_parsed.get("dependencies", [])[:10]:
            dependencies.append({
                "name": dep,
                "type": "python-package",
                "role": "dependency",
                "confidence": 0.9,
            })
        
        for db in py_parsed.get("databases", []):
            dependencies.append({
                "name": db,
                "type": "database",
                "role": "infrastructure",
                "confidence": 0.8,
            })
    
    if js_parsed:
        for dep in js_parsed.get("dependencies", [])[:10]:
            dependencies.append({
                "name": dep,
                "type": "npm-package",
                "role": "dependency",
                "confidence": 0.9,
            })
    
    if compose_parsed:
        for svc in compose_parsed.get("services", []):
            dependencies.append({
                "name": svc,
                "type": "docker-service",
                "role": "service",
                "confidence": 0.9,
            })
    
    if env_parsed:
        categories = env_parsed.get("inferred_categories", {})
        for cat, vars in categories.items():
            dependencies.append({
                "name": f"{cat} (env vars: {', '.join(vars[:3])})",
                "type": "external-service",
                "role": "inferred",
                "confidence": 0.5,
            })
    
    return dependencies


def extract_all_signals(repo_path: str) -> Dict[str, Any]:
    """Extract all signals from a repository."""
    repo_name = os.path.basename(repo_path.rstrip(os.sep))
    root = Path(repo_path)
    
    structure = get_top_level_structure(repo_path)
    
    parsed_files = {}
    
    readme_path = root / "README.md"
    if readme_path.exists():
        content = read_file_safe(str(readme_path))
        if content:
            parsed_files["readme"] = parse_readme(content)
    
    req_path = root / "requirements.txt"
    if req_path.exists():
        content = read_file_safe(str(req_path))
        if content:
            parsed_files["requirements"] = parse_requirements_txt(content)
    
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        content = read_file_safe(str(pyproject_path))
        if content:
            parsed_files["pyproject"] = parse_pyproject_toml(content)
            if not parsed_files["pyproject"].get("project_name"):
                parsed_files["pyproject"]["project_name"] = pyproject_path.stem
    
    package_path = root / "package.json"
    if package_path.exists():
        content = read_file_safe(str(package_path))
        if content:
            parsed_files["package"] = parse_package_json(content)
            if not parsed_files["package"].get("project_name"):
                parsed_files["package"]["project_name"] = package_path.stem
    
    compose_path = None
    for name in ["docker-compose.yml", "docker-compose.yaml", "docker-compose.prod.yml"]:
        p = root / name
        if p.exists():
            compose_path = p
            break
    
    if compose_path:
        content = read_file_safe(str(compose_path))
        if content:
            parsed_files["docker_compose"] = parse_docker_compose(content)
    
    dockerfile_path = root / "Dockerfile"
    if dockerfile_path.exists():
        content = read_file_safe(str(dockerfile_path))
        if content:
            parsed_files["dockerfile"] = parse_dockerfile(content)
    
    env_example_path = root / ".env.example"
    if env_example_path.exists():
        content = read_file_safe(str(env_example_path))
        if content:
            parsed_files["env_example"] = parse_env_example(content)
    
    makefile_path = root / "Makefile"
    if makefile_path.exists():
        content = read_file_safe(str(makefile_path))
        if content:
            parsed_files["makefile"] = parse_makefile(content)
    
    project_type = infer_project_type(structure, parsed_files)
    
    languages = []
    frameworks = []
    
    if parsed_files.get("requirements") or parsed_files.get("pyproject"):
        languages.append("Python")
        for fw in parsed_files.get("pyproject", {}).get("frameworks", []):
            frameworks.append(fw)
        for fw in parsed_files.get("requirements", {}).get("frameworks", []):
            frameworks.append(fw)
    
    if parsed_files.get("package"):
        languages.append("JavaScript/TypeScript")
        for fw in parsed_files.get("package", {}).get("frameworks", []):
            frameworks.append(fw)
    
    if parsed_files.get("dockerfile"):
        if parsed_files.get("dockerfile", {}).get("base_image"):
            img = parsed_files["dockerfile"]["base_image"]
            if "python" in img.lower():
                if "Python" not in languages:
                    languages.append("Python")
            if "node" in img.lower():
                if "JavaScript/TypeScript" not in languages:
                    languages.append("JavaScript/TypeScript")
    
    databases = []
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    if py_parsed:
        databases.extend(py_parsed.get("databases", []))
    
    if parsed_files.get("docker_compose"):
        compose = parsed_files["docker_compose"]
        for svc in compose.get("services", []):
            for db_type, patterns in SERVICE_INDICATORS.items():
                if any(p in svc.lower() for p in patterns):
                    if db_type.title() not in databases:
                        databases.append(db_type.title())
    
    infrastructure = []
    if parsed_files.get("dockerfile"):
        infrastructure.append("Docker")
    if parsed_files.get("docker_compose"):
        infrastructure.append("Docker Compose")
    if parsed_files.get("makefile"):
        infrastructure.append("Make")
    if parsed_files.get("env_example"):
        infrastructure.append("Environment Config")
    
    external_services = []
    py_parsed = parsed_files.get("pyproject") or parsed_files.get("requirements")
    if py_parsed:
        for dep in py_parsed.get("dependencies", []):
            for svc, patterns in CLOUDS.items():
                if svc in dep.lower():
                    if patterns not in external_services:
                        external_services.append(patterns)
    
    components = detect_components(structure, parsed_files)
    flows = detect_flows(components, parsed_files)
    dependencies = detect_dependencies(parsed_files)
    
    readme = parsed_files.get("readme", {})
    summary = readme.get("first_paragraph", "") or f"Repository: {repo_name}"
    
    assumptions = []
    open_questions = []
    uncertainties = []
    
    if not languages:
        assumptions.append("Could not detect primary language - inferred from structure")
        open_questions.append("What is the primary language/framework?")
        uncertainties.append("Language detection inconclusive")
    
    if not frameworks:
        assumptions.append("No explicit framework detected - may be a library or script")
        open_questions.append("What framework(s) are used?")
    
    if not components:
        assumptions.append("Could not detect distinct components")
        open_questions.append("What are the main components?")
    
    if not flows:
        assumptions.append("Could not infer data flows between components")
        open_questions.append("How do components communicate?")
        uncertainties.append("Flow analysis incomplete")
    
    if parsed_files.get("docker_compose"):
        services = parsed_files["docker_compose"].get("services", [])
        if len(services) > 3:
            open_questions.append("Are there more services in production docker-compose?")
    
    if not parsed_files.get("env_example"):
        open_questions.append("No .env.example found - what environment variables are needed?")
    
    project_name = parsed_files.get("pyproject", {}).get("project_name") or \
                   parsed_files.get("package", {}).get("project_name") or \
                   repo_name
    
    return {
        "project_name": project_name,
        "project_type": project_type,
        "summary": summary,
        "stack": {
            "languages": list(set(languages)),
            "frameworks": list(set(frameworks)),
            "databases": list(set(databases)),
            "infrastructure": list(set(infrastructure)),
            "external_services": list(set(external_services)),
        },
        "structure": structure,
        "parsed_files": {k: v for k, v in parsed_files.items() if k != "readme"},
        "components": components,
        "flows": flows,
        "dependencies": dependencies,
        "assumptions": assumptions,
        "open_questions": open_questions,
        "uncertainties": uncertainties,
    }
