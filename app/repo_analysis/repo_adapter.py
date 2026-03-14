"""Repository source adapter — produces ExtractedSignals from a cloned repo.

This is Layer B for the repository source type.
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

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
    classify_dependency,
)
from app.repo_analysis.signals_model import (
    ComponentSignal,
    DatabaseSignal,
    DependencySignal,
    ExtractedSignals,
    ExternalServiceSignal,
    FlowSignal,
    FrameworkSignal,
    InfrastructureSignal,
    LanguageSignal,
    SourceMetadata,
    signals_to_context_dict,
)
from app.repo_analysis.context_normalizer import normalize_signals


COMMON_DIR_PATTERNS = {
    "frontend": ["frontend", "client", "web", "ui", "public", "static", "pages", "components", "app"],
    "backend": ["backend", "server", "api", "service", "app", "src", "routes", "endpoints", "controllers"],
    "worker": ["worker", "workers", "jobs", "tasks", "celery", "scheduler", "rq", "background"],
    "database": ["db", "database", "migrations", "alembic", "models", "entities"],
    "config": ["config", "configs", "configuration", "settings"],
    "tests": ["tests", "test", "__tests__", "specs", "e2e"],
    "infra": ["infra", "infrastructure", "terraform", "cloudformation", "kubernetes", "k8s", "deploy"],
    "docker": ["docker"],
    "docs": ["docs", "documentation"],
    "scripts": ["scripts", "tools", "bin", "migrations"],
}

ENTRY_POINT_FILES = {
    "main.py": "api",
    "app.py": "api", 
    "server.py": "api",
    "manage.py": "django",
    "cli.py": "cli",
    "main.js": "frontend",
    "index.js": "frontend",
    "server.js": "api",
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

EXTERNAL_SERVICE_PATTERNS = {
    "whatsapp": ["whatsapp", "meta", "whatsapp cloud api"],
    "stripe": ["stripe", "payment"],
    "twilio": ["twilio", "sms", "voice"],
    "sendgrid": ["sendgrid", "email", "ses"],
    "aws": ["aws", "s3", "sqs", "sns"],
    "google": ["google cloud", "gcp", "firestore"],
    "auth0": ["auth0", "auth", "oauth"],
    "okta": ["okta", "saml"],
}

CLOUDS = {
    "aws": "AWS",
    "google-cloud": "Google Cloud",
    "azure": "Azure",
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


def get_all_file_paths(repo_path: str, max_depth: int = 3) -> List[str]:
    """Get all file paths up to max_depth levels."""
    root = Path(repo_path)
    files = []
    
    try:
        for path in root.rglob("*"):
            if path.is_file():
                depth = len(path.relative_to(root).parts)
                if depth <= max_depth:
                    rel_path = str(path.relative_to(root))
                    if not any(p.startswith(".") or p in ["node_modules", "__pycache__", "venv", ".git"] for p in path.parts):
                        files.append(rel_path)
    except Exception:
        pass
    
    return files


def detect_entry_points(files: List[str]) -> Dict[str, str]:
    """Detect entry point files and their likely purposes."""
    entry_points = {}
    for f in files:
        fname = Path(f).name
        if fname in ENTRY_POINT_FILES:
            entry_points[fname] = ENTRY_POINT_FILES[fname]
        
        # Check for common entry point patterns
        if "main" in fname and fname.endswith(".py"):
            entry_points[f] = "api"
        if "server" in fname and fname.endswith((".py", ".js", ".ts")):
            entry_points[f] = "api"
    
    return entry_points


def infer_project_type(structure: Dict, parsed: Dict) -> str:
    """Infer project type."""
    dirs = structure.get("directories", [])
    files = structure.get("files", [])
    
    has_py = any(f in ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"] for f in files)
    has_js = "package.json" in files
    
    py_frameworks = parsed.get("pyproject", {}).get("frameworks", []) + parsed.get("requirements", {}).get("frameworks", [])
    js_frameworks = parsed.get("package", {}).get("frameworks", [])
    
    has_frontend = any(d in dirs for d in COMMON_DIR_PATTERNS["frontend"])
    has_backend = any(d in dirs for d in COMMON_DIR_PATTERNS["backend"])
    has_worker = any(d in dirs for d in COMMON_DIR_PATTERNS["worker"])
    
    if has_py and has_frontend:
        return "fullstack"
    elif has_py:
        if "FastAPI" in py_frameworks or "Flask" in py_frameworks:
            return "api"
        elif "Django" in py_frameworks:
            return "django"
        return "python"
    elif has_js:
        if any(fw in js_frameworks for fw in ["React", "Next.js", "Vue.js"]):
            return "frontend"
        elif "Express" in js_frameworks or "Fastify" in js_frameworks:
            return "api"
        return "javascript"
    elif has_backend and has_frontend:
        return "fullstack"
    else:
        return "unknown"


def _get_deps_with_roles(parsed: Dict) -> List[Dict]:
    """Get dependencies with their roles from parsed files."""
    all_deps = []
    
    for key in ["pyproject", "requirements"]:
        if parsed.get(key) and parsed[key].get("dependencies"):
            deps = parsed[key]["dependencies"]
            if deps and isinstance(deps[0], dict):
                all_deps.extend(deps)
            else:
                for dep in deps:
                    all_deps.append({"name": dep, "role": classify_dependency(dep)})
    
    if parsed.get("package") and parsed["package"].get("dependencies"):
        deps = parsed["package"]["dependencies"]
        if deps and isinstance(deps[0], dict):
            all_deps.extend(deps)
        else:
            for dep in deps:
                all_deps.append({"name": dep, "role": classify_dependency(dep)})
    
    return all_deps


def parse_repo(repo_path: str, repo_url: str = "local") -> ExtractedSignals:
    """Parse a cloned repository and produce source-agnostic ExtractedSignals.
    
    This is the main entry point for repo source extraction (Layer B -> Layer C).
    """
    repo_name = os.path.basename(repo_path.rstrip(os.sep))
    root = Path(repo_path)
    
    structure = get_top_level_structure(repo_path)
    all_files = get_all_file_paths(repo_path)
    entry_points = detect_entry_points(all_files)
    
    parsed = {}
    
    # Parse README
    readme_path = root / "README.md"
    readme_text = ""
    if readme_path.exists():
        content = read_file_safe(str(readme_path))
        if content:
            parsed["readme"] = parse_readme(content)
            readme_text = content
    
    # Parse requirements.txt
    req_path = root / "requirements.txt"
    if req_path.exists():
        content = read_file_safe(str(req_path))
        if content:
            parsed["requirements"] = parse_requirements_txt(content)
    
    # Parse pyproject.toml
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        content = read_file_safe(str(pyproject_path))
        if content:
            parsed["pyproject"] = parse_pyproject_toml(content)
    
    # Parse package.json
    package_path = root / "package.json"
    if package_path.exists():
        content = read_file_safe(str(package_path))
        if content:
            parsed["package"] = parse_package_json(content)
    
    # Parse docker-compose.yml
    for name in ["docker-compose.yml", "docker-compose.yaml", "docker-compose.prod.yml", "docker-compose.dev.yml"]:
        p = root / name
        if p.exists():
            content = read_file_safe(str(p))
            if content:
                parsed["docker_compose"] = parse_docker_compose(content)
            break
    
    # Parse Dockerfile
    dockerfile_path = root / "Dockerfile"
    if dockerfile_path.exists():
        content = read_file_safe(str(dockerfile_path))
        if content:
            parsed["dockerfile"] = parse_dockerfile(content)
    
    # Parse .env.example
    env_example_path = root / ".env.example"
    if env_example_path.exists():
        content = read_file_safe(str(env_example_path))
        if content:
            parsed["env_example"] = parse_env_example(content)
    
    # Parse Makefile
    makefile_path = root / "Makefile"
    if makefile_path.exists():
        content = read_file_safe(str(makefile_path))
        if content:
            parsed["makefile"] = parse_makefile(content)
    
    # Get all dependencies with roles
    all_deps = _get_deps_with_roles(parsed)
    dep_names = [d["name"].lower() for d in all_deps]
    dep_by_role = {}
    for d in all_deps:
        role = d.get("role", "application_dependency")
        dep_by_role.setdefault(role, []).append(d["name"])
    
    project_type = infer_project_type(structure, parsed)
    
    # Detect languages
    languages = []
    frameworks = []
    databases = []
    infrastructure = []
    external_services = []
    
    if parsed.get("requirements") or parsed.get("pyproject"):
        languages.append(LanguageSignal(name="Python", confidence=0.9))
        
        for fw in parsed.get("pyproject", {}).get("frameworks", []):
            frameworks.append(FrameworkSignal(name=fw, confidence=0.8))
        for fw in parsed.get("requirements", {}).get("frameworks", []):
            if fw not in [f.name for f in frameworks]:
                frameworks.append(FrameworkSignal(name=fw, confidence=0.8))
    
    if parsed.get("package"):
        languages.append(LanguageSignal(name="JavaScript/TypeScript", confidence=0.9))
        for fw in parsed.get("package", {}).get("frameworks", []):
            frameworks.append(FrameworkSignal(name=fw, confidence=0.8))
    
    if parsed.get("dockerfile"):
        infrastructure.append(InfrastructureSignal(name="Docker", category="container", confidence=0.9))
        base_img = parsed.get("dockerfile", {}).get("base_image", "")
        if "python" in base_img.lower() and not any(l.name == "Python" for l in languages):
            languages.append(LanguageSignal(name="Python", confidence=0.7))
        if "node" in base_img.lower() and not any(l.name == "JavaScript/TypeScript" for l in languages):
            languages.append(LanguageSignal(name="JavaScript/TypeScript", confidence=0.7))
    
    # Detect databases from dependencies
    databases = []
    for role, deps in dep_by_role.items():
        if role in ["database_driver", "orm"]:
            for d in deps:
                d_lower = d.lower()
                if "postgres" in d_lower or "psycopg" in d_lower:
                    databases.append(DatabaseSignal(name="PostgreSQL", type="relational", confidence=0.9))
                elif "mysql" in d_lower:
                    databases.append(DatabaseSignal(name="MySQL", type="relational", confidence=0.9))
                elif "mongo" in d_lower:
                    databases.append(DatabaseSignal(name="MongoDB", type="document", confidence=0.9))
    
    # Add databases from docker-compose
    if parsed.get("docker_compose"):
        infrastructure.append(InfrastructureSignal(name="Docker Compose", category="container", confidence=0.9))
        for svc in parsed["docker_compose"].get("services", []):
            for db_type, patterns in SERVICE_INDICATORS.items():
                if any(p in svc.lower() for p in patterns):
                    if db_type.title() not in [d.name for d in databases]:
                        databases.append(DatabaseSignal(name=db_type.title(), type="relational", confidence=0.8))
    
    # Infrastructure
    infrastructure = []
    if parsed.get("dockerfile"):
        infrastructure.append(InfrastructureSignal(name="Docker", category="container", confidence=0.9))
    if parsed.get("docker_compose"):
        infrastructure.append(InfrastructureSignal(name="Docker Compose", category="container", confidence=0.9))
    if parsed.get("makefile"):
        infrastructure.append(InfrastructureSignal(name="Make", category="build_tool", confidence=0.7))
    if parsed.get("env_example"):
        infrastructure.append(InfrastructureSignal(name="Environment Config", category="configuration", confidence=0.7))
    
    # External services from README and env
    external_services = []
    readme_lower = readme_text.lower()
    for svc, patterns in EXTERNAL_SERVICE_PATTERNS.items():
        if any(p in readme_lower for p in patterns):
            external_services.append(ExternalServiceSignal(
                name=svc.replace("_", " ").title(),
                category="external_integration",
                confidence=0.8
            ))
    
    # Detect components
    components = _detect_components(structure, parsed, dep_by_role, entry_points, readme_text)
    
    # Detect flows
    flows = _detect_flows(components, parsed, dep_by_role, readme_text)
    
    # Detect dependencies with roles
    dependencies = _detect_dependencies(parsed, all_deps)
    
    # Generate summary
    readme = parsed.get("readme", {})
    summary = readme.get("first_paragraph", "") or f"Repository: {repo_name}"
    
    # Generate assumptions and questions
    assumptions, open_questions, uncertainties = _generate_questions_and_assumptions(
        components, parsed, dep_by_role, readme_text, structure
    )
    
    project_name = parsed.get("pyproject", {}).get("project_name") or \
                   parsed.get("package", {}).get("project_name") or \
                   repo_name
    
    return ExtractedSignals(
        version=1,
        project_name=project_name,
        project_type=project_type,
        summary=summary,
        source_metadata=SourceMetadata(
            source_type="repo",
            source_id=repo_url,
            extraction_method="heuristics",
            confidence=0.8,
        ),
        languages=languages,
        frameworks=frameworks,
        databases=databases,
        infrastructure=infrastructure,
        external_services=external_services,
        components=components,
        flows=flows,
        dependencies=dependencies,
        assumptions=assumptions,
        open_questions=open_questions,
        uncertainties=uncertainties,
        raw_signals={"structure": structure, "parsed": {k: v for k, v in parsed.items() if k != "readme"}},
    )


def _detect_components(structure: Dict, parsed: Dict, dep_by_role: Dict, entry_points: Dict, readme_text: str) -> List[ComponentSignal]:
    """Detect components from structure and parsed files."""
    components = []
    dirs = structure.get("directories", [])
    files = structure.get("files", [])
    readme_lower = readme_text.lower()
    
    py_frameworks = parsed.get("pyproject", {}).get("frameworks", []) + parsed.get("requirements", {}).get("frameworks", [])
    js_frameworks = parsed.get("package", {}).get("frameworks", [])
    docker_services = parsed.get("docker_compose", {}).get("services", [])
    
    # API Component
    has_api = (
        any(d in dirs for d in COMMON_DIR_PATTERNS["backend"]) or
        any(f in files for f in ["main.py", "app.py", "server.py", "main.ts", "main.js"]) or
        any(f in entry_points.values() for f in ["api"]) or
        any("fastapi" in f.lower() for f in py_frameworks) or
        any("express" in f.lower() for f in js_frameworks) or
        "api" in docker_services or
        "gateway" in docker_services
    )
    
    if has_api:
        api_tech = []
        if "FastAPI" in py_frameworks:
            api_tech.append("FastAPI")
        elif "Flask" in py_frameworks:
            api_tech.append("Flask")
        elif "Django" in py_frameworks:
            api_tech.append("Django")
        elif "Express" in js_frameworks:
            api_tech.append("Express")
        
        components.append(ComponentSignal(
            name="api",
            component_type="api",
            description="Main API service handling HTTP requests",
            technologies=api_tech or ["Python", "Node.js"],
            detected_from=["directory_structure", "entry_points", "dependencies", "docker_compose"],
            confidence=0.85,
        ))
    
    # Frontend Component
    has_frontend = (
        any(d in dirs for d in COMMON_DIR_PATTERNS["frontend"]) or
        "package.json" in files or
        any("react" in f.lower() for f in js_frameworks) or
        any("vue" in f.lower() for f in js_frameworks) or
        any("next" in f.lower() for f in js_frameworks) or
        "frontend" in docker_services or
        "client" in docker_services or
        "web" in docker_services
    )
    
    if has_frontend:
        frontend_tech = []
        if "React" in js_frameworks:
            frontend_tech.append("React")
        if "Next.js" in js_frameworks:
            frontend_tech.append("Next.js")
        if "Vue.js" in js_frameworks:
            frontend_tech.append("Vue.js")
        
        components.append(ComponentSignal(
            name="frontend",
            component_type="frontend",
            description="Frontend application",
            technologies=frontend_tech or ["JavaScript/TypeScript"],
            detected_from=["directory_structure", "package.json", "dependencies"],
            confidence=0.85,
        ))
    
    # Worker Component
    has_worker = (
        any(d in dirs for d in COMMON_DIR_PATTERNS["worker"]) or
        "celery" in dep_by_role.get("task_queue", []) or
        "rq" in dep_by_role.get("task_queue", []) or
        "worker" in docker_services or
        "workers" in docker_services or
        "rq-worker" in docker_services or
        ("background" in readme_lower and ("job" in readme_lower or "queue" in readme_lower))
    )
    
    if has_worker:
        worker_tech = []
        if "celery" in dep_by_role.get("task_queue", []):
            worker_tech.append("Celery")
        if "rq" in dep_by_role.get("task_queue", []):
            worker_tech.append("RQ")
        
        components.append(ComponentSignal(
            name="worker",
            component_type="worker",
            description="Background job processor",
            technologies=worker_tech or ["Python"],
            detected_from=["directory_structure", "dependencies", "docker_compose", "readme"],
            confidence=0.8,
        ))
    
    # Database Component
    has_database = (
        any(db in dirs for db in ["db", "database", "migrations", "alembic"]) or
        "sqlalchemy" in dep_by_role.get("orm", []) or
        "alembic" in dep_by_role.get("migrations", []) or
        any("postgres" in s.lower() for s in docker_services) or
        any("mysql" in s.lower() for s in docker_services) or
        "db" in docker_services or
        "database" in docker_services
    )
    
    if has_database:
        db_tech = []
        if "sqlalchemy" in dep_by_role.get("orm", []):
            db_tech.append("SQLAlchemy")
        if "alembic" in dep_by_role.get("migrations", []):
            db_tech.append("Alembic")
        
        components.append(ComponentSignal(
            name="database",
            component_type="database",
            description="Primary database for persistent storage",
            technologies=db_tech or ["PostgreSQL"],
            detected_from=["directory_structure", "dependencies", "docker_compose"],
            confidence=0.85,
        ))
    
    # Cache/Queue Component
    has_cache = (
        "redis" in dep_by_role.get("cache_broker", []) or
        "redis" in dep_by_role.get("task_queue", []) or
        "redis" in docker_services or
        "cache" in docker_services
    )
    
    if has_cache:
        cache_tech = []
        if "redis" in dep_by_role.get("cache_broker", []) or "redis" in dep_by_role.get("task_queue", []):
            cache_tech.append("Redis")
        
        desc = "Redis for caching and session storage"
        if "rq" in dep_by_role.get("task_queue", []) or "celery" in dep_by_role.get("task_queue", []):
            desc = "Redis for job queue and caching"
        
        components.append(ComponentSignal(
            name="cache",
            component_type="cache",
            description=desc,
            technologies=cache_tech or ["Redis"],
            detected_from=["dependencies", "docker_compose"],
            confidence=0.8,
        ))
    
    # External Service Components (from README)
    for svc, patterns in EXTERNAL_SERVICE_PATTERNS.items():
        if any(p in readme_lower for p in patterns):
            svc_name = svc.replace("_", " ")
            if svc == "whatsapp":
                components.append(ComponentSignal(
                    name="whatsapp_api",
                    component_type="external_service",
                    description="WhatsApp Cloud API integration for messaging",
                    technologies=["WhatsApp Cloud API"],
                    detected_from=["readme"],
                    confidence=0.8,
                ))
            elif svc == "stripe":
                components.append(ComponentSignal(
                    name="payment_gateway",
                    component_type="external_service",
                    description="Stripe payment processing",
                    technologies=["Stripe"],
                    detected_from=["readme"],
                    confidence=0.8,
                ))
    
    if not components:
        components.append(ComponentSignal(
            name="application",
            component_type="service",
            description="Main application",
            technologies=[],
            detected_from=["inference"],
            confidence=0.5,
        ))
    
    return components


def _detect_flows(components: List[ComponentSignal], parsed: Dict, dep_by_role: Dict, readme_text: str) -> List[FlowSignal]:
    """Detect flows between components."""
    flows = []
    readme_lower = readme_text.lower()
    
    comp_by_type = {c.component_type: c for c in components}
    comp_by_name = {c.name: c for c in components}
    
    # API -> Database (ORM)
    if "api" in comp_by_type and "database" in comp_by_type:
        if "orm" in dep_by_role:
            flows.append(FlowSignal(
                name="api_to_database",
                source="api",
                target="database",
                flow_type="data",
                description="API queries database via SQLAlchemy ORM",
                confidence=0.85,
            ))
    
    # API -> Cache (Redis)
    if "api" in comp_by_type and "cache" in comp_by_type:
        flows.append(FlowSignal(
            name="api_to_cache",
            source="api",
            target="cache",
            flow_type="data",
            description="API uses Redis for caching and session storage",
            confidence=0.75,
        ))
    
    # API -> Cache (Job Queue)
    if "api" in comp_by_type and "cache" in comp_by_type:
        if "task_queue" in dep_by_role or "rq" in dep_by_role.get("task_queue", []):
            flows.append(FlowSignal(
                name="api_to_queue",
                source="api",
                target="cache",
                flow_type="message",
                description="API enqueues jobs to Redis/RQ",
                confidence=0.8,
            ))
    
    # Worker -> Cache (Job Queue)
    if "worker" in comp_by_type and "cache" in comp_by_type:
        if "task_queue" in dep_by_role:
            flows.append(FlowSignal(
                name="worker_from_queue",
                source="cache",
                target="worker",
                flow_type="message",
                description="Worker picks up jobs from Redis queue",
                confidence=0.8,
            ))
    
    # Worker -> Database
    if "worker" in comp_by_type and "database" in comp_by_type:
        flows.append(FlowSignal(
            name="worker_to_database",
            source="worker",
            target="database",
            flow_type="data",
            description="Worker queries database for job processing",
            confidence=0.7,
        ))
    
    # Frontend -> API
    if "frontend" in comp_by_type and "api" in comp_by_type:
        flows.append(FlowSignal(
            name="frontend_to_api",
            source="frontend",
            target="api",
            flow_type="http",
            description="Frontend makes HTTP API requests",
            confidence=0.85,
        ))
    
    # External -> API (Webhooks)
    for comp in components:
        if comp.component_type == "external_service":
            if "whatsapp" in comp.name.lower():
                flows.append(FlowSignal(
                    name="whatsapp_to_api",
                    source="whatsapp_api",
                    target="api",
                    flow_type="http",
                    description="WhatsApp Cloud API sends webhooks to API",
                    confidence=0.85,
                ))
    
    # API architecture from README
    if "arch" in readme_lower or "architecture" in readme_lower:
        if "whatsapp" in readme_lower and "api" in readme_lower:
            if not any(f.source == "whatsapp_api" and f.target == "api" for f in flows):
                flows.append(FlowSignal(
                    name="messaging_to_api",
                    source="external_messaging",
                    target="api",
                    flow_type="http",
                    description="External messaging service sends webhooks",
                    confidence=0.6,
                ))
    
    return flows


def _detect_dependencies(parsed: Dict, all_deps: List[Dict]) -> List[DependencySignal]:
    """Detect external dependencies with roles."""
    dependencies = []
    
    seen = set()
    for dep in all_deps[:20]:
        name = dep.get("name", "")
        role = dep.get("role", classify_dependency(name))
        
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        
        dependencies.append(DependencySignal(
            name=name,
            dependency_type="python-package" if "python" in role else "npm-package",
            role=role,
            confidence=0.85,
        ))
    
    # Add docker services
    for svc in parsed.get("docker_compose", {}).get("services", []):
        dependencies.append(DependencySignal(
            name=svc,
            dependency_type="docker-service",
            role="infrastructure",
            confidence=0.9,
        ))
    
    return dependencies


def _generate_questions_and_assumptions(components: List[ComponentSignal], parsed: Dict, dep_by_role: Dict, readme_text: str, structure: Dict) -> tuple:
    """Generate useful architecture questions and assumptions."""
    assumptions = []
    open_questions = []
    uncertainties = []
    
    has_api = any(c.component_type == "api" for c in components)
    has_worker = any(c.component_type == "worker" for c in components)
    has_database = any(c.component_type == "database" for c in components)
    has_cache = any(c.component_type == "cache" for c in components)
    
    readme_lower = readme_text.lower()
    
    # Assumptions based on what's detected
    if has_api and has_database:
        assumptions.append("API likely uses database for persistent storage")
    
    if has_cache and has_worker:
        assumptions.append("Background jobs likely use Redis queue")
    
    if "multi-tenant" in readme_lower or "multitenant" in readme_lower:
        assumptions.append("Multi-tenant architecture detected from README")
        open_questions.append("What is the tenant isolation strategy (schema-level, database-level, or host-based)?")
    
    if "whatsapp" in readme_lower or "whatsapp" in str(parsed.get("env_example", {})).lower():
        assumptions.append("WhatsApp Cloud API integration for messaging")
        open_questions.append("How are WhatsApp webhooks authenticated and rate-limited?")
    
    # Database questions
    if not has_database:
        open_questions.append("What database is used for persistent storage?")
    else:
        open_questions.append("What is the database migration strategy?")
    
    # Cache/Queue questions
    if not has_cache and has_worker:
        open_questions.append("Is Redis needed for job queuing or caching?")
    
    # Background jobs
    if not has_worker:
        open_questions.append("Are there background jobs or async processing needs?")
        open_questions.append("What triggers background job processing?")
    
    # Auth questions
    if "auth" not in dep_by_role:
        open_questions.append("What authentication/authorization approach is used?")
        open_questions.append("How are API keys or tokens managed?")
    
    # Deployment questions
    if not parsed.get("docker_compose"):
        open_questions.append("How is the application containerized for deployment?")
        open_questions.append("What is the deployment target (bare metal, k8s, serverless)?")
    else:
        open_questions.append("Are there production-specific docker-compose configurations?")
    
    # Multi-tenancy
    if "tenant" in readme_lower:
        open_questions.append("How is multi-tenancy implemented (database, schema, or code-level)?")
    
    # External integrations
    if not any(c.component_type == "external_service" for c in components):
        if any(p in readme_lower for p in ["api", "integration", "webhook", "third-party"]):
            open_questions.append("What external services or APIs does this application integrate with?")
    
    # Secrets
    env_example = parsed.get("env_example", {})
    if not env_example or not env_example.get("env_vars"):
        open_questions.append("What environment variables are required for deployment?")
        open_questions.append("What secrets need to be managed (API keys, database credentials)?")
    
    # Scaling
    if has_worker:
        open_questions.append("How are workers scaled (horizontal pod autoscaling, number of replicas)?")
        open_questions.append("What happens when a job fails - retry policy?")
    
    # Observability
    if "observability" not in dep_by_role:
        open_questions.append("What logging, monitoring, and alerting is configured?")
    
    # Uncertainties
    if not has_database and not has_cache:
        uncertainties.append("No clear data storage detected - may use external service")
    
    if not has_api and not has_worker:
        uncertainties.append("No clear compute component detected - unclear application type")
    
    if not parsed.get("docker_compose"):
        uncertainties.append("No containerization detected - deployment approach unclear")
    
    if "env_example" not in parsed:
        uncertainties.append("No .env.example found - configuration management unclear")
    
    return assumptions, open_questions, uncertainties


def analyze_repo(repo_path: str, repo_url: str = "local") -> Dict[str, Any]:
    """Main entry point: parse repo and return canonical context dict.
    
    Returns a dict ready for the merge/normalization pipeline.
    """
    signals = parse_repo(repo_path, repo_url)
    context_dict = signals_to_context_dict(signals)
    return normalize_signals([context_dict])
