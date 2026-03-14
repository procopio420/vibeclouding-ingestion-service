"""Lightweight file parsers for repo analysis."""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


PYTHON_FRAMEWORKS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "bottle": "Bottle",
    "tornado": "Tornado",
    "pyramid": "Pyramid",
    "starlette": "Starlette",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "celery": "Celery",
    "redis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "pydantic": "Pydantic",
    "django-rest-framework": "Django REST Framework",
    "channels": "Django Channels",
    "httpx": "httpx",
    "requests": "requests",
    "aiohttp": "aiohttp",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "pytest": "pytest",
    "playwright": "Playwright",
    "selenium": "Selenium",
    "scrapy": "Scrapy",
}

JS_FRAMEWORKS = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "nuxt": "Nuxt",
    "express": "Express",
    "fastify": "Fastify",
    "nest": "NestJS",
    "hapi": "Hapi",
    "koa": "Koa",
    "sails": "Sails",
    "feathers": "Feathers",
    "gatsby": "Gatsby",
    "vite": "Vite",
    "webpack": "Webpack",
    "parcel": "Parcel",
    "axios": "axios",
    "node-fetch": "node-fetch",
}

DATABASES = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "dynamodb": "DynamoDB",
    "elasticsearch": "Elasticsearch",
    "cassandra": "Cassandra",
    "couchdb": "CouchDB",
    "influxdb": "InfluxDB",
    "timeseries": "TimescaleDB",
    "neptune": "Neptune",
    "sqlalchemy": "SQLAlchemy",
    "prisma": "Prisma",
}

DEPENDENCY_ROLES = {
    # ORM / Data Layer
    "sqlalchemy": "orm",
    "alembic": "migrations",
    "django-orm": "orm",
    "tortoise-orm": "orm",
    "pony": "orm",
    "mongoengine": "orm",
    
    # Database Drivers
    "psycopg2": "database_driver",
    "psycopg2-binary": "database_driver",
    "asyncpg": "database_driver",
    "aiomysql": "database_driver",
    "pymongo": "database_driver",
    "mysql-connector-python": "database_driver",
    "pymysql": "database_driver",
    "sqlite3": "database_driver",
    
    # Cache / Queue / Jobs
    "redis": "cache_broker",
    "celery": "task_queue",
    "rq": "task_queue",
    "kombu": "task_queue",
    "huey": "task_queue",
    "dramatiq": "task_queue",
    
    # Validation / Config
    "pydantic": "validation",
    "pydantic-settings": "config",
    "python-dotenv": "config",
    "dynaconf": "config",
    "hydra": "config",
    
    # Runtime Servers
    "uvicorn": "runtime_server",
    "gunicorn": "runtime_server",
    "hypercorn": "runtime_server",
    "daphne": "runtime_server",
    "waitress": "runtime_server",
    "bjoern": "runtime_server",
    
    # HTTP Clients
    "httpx": "http_client",
    "requests": "http_client",
    "aiohttp": "http_client",
    "urllib3": "http_client",
    
    # Cloud SDKs
    "boto3": "cloud_sdk",
    "google-cloud": "cloud_sdk",
    "azure": "cloud_sdk",
    "stripe": "payment_gateway",
    
    # Testing
    "pytest": "testing",
    "pytest-asyncio": "testing",
    "pytest-cov": "testing",
    "pytest-mock": "testing",
    "httpx": "testing",
    "responses": "testing",
    "factory-boy": "testing",
    "jest": "testing",
    "vitest": "testing",
    "mocha": "testing",
    
    # Linting / Typecheck / Formatting
    "ruff": "linting",
    "mypy": "type_check",
    "pyright": "type_check",
    "eslint": "linting",
    "prettier": "formatting",
    "black": "formatting",
    "isort": "formatting",
    "pre-commit": "development_tool",
    
    # Auth
    "passlib": "auth",
    "python-jose": "auth",
    "pyjwt": "auth",
    "Authlib": "auth",
    "django-allauth": "auth",
    "bcrypt": "auth",
    "cryptography": "auth",
    
    # Templating
    "jinja2": "templating",
    "jinja2": "templating",
    "mako": "templating",
    "chevron": "templating",
    
    # API Frameworks
    "fastapi": "api_framework",
    "flask": "api_framework",
    "django": "api_framework",
    "bottle": "api_framework",
    "express": "api_framework",
    "nestjs": "api_framework",
    "koa": "api_framework",
    
    # Serialization
    "orjson": "serialization",
    "ujson": "serialization",
    "msgpack": "serialization",
    "pyyaml": "serialization",
    "toml": "serialization",
    "xmltodict": "serialization",
    
    # Observability
    "sentry-sdk": "observability",
    "opentelemetry-api": "observability",
    "prometheus-client": "observability",
    "structlog": "logging",
    "loguru": "logging",
    
    # Background Jobs / Workers
    "huey": "task_queue",
    "schedule": "scheduler",
}


def classify_dependency(dep_name: str) -> str:
    """Classify a dependency by its architectural role."""
    dep_lower = dep_name.lower()
    
    # Direct match
    if dep_lower in DEPENDENCY_ROLES:
        return DEPENDENCY_ROLES[dep_lower]
    
    # Partial matches for common patterns
    if "pytest" in dep_lower:
        return "testing"
    if "test" in dep_lower:
        return "testing"
    if "mock" in dep_lower:
        return "testing"
    
    if "lint" in dep_lower or "ruff" in dep_lower:
        return "linting"
    
    if "type" in dep_lower or "mypy" in dep_lower or "pyright" in dep_lower:
        return "type_check"
    
    if "sqlalchemy" in dep_lower or "orm" in dep_lower:
        return "orm"
    
    if "alembic" in dep_lower or "migration" in dep_lower:
        return "migrations"
    
    if any(db in dep_lower for db in ["postgres", "mysql", "mongo", "sqlite", "redis"]):
        return "database_driver"
    
    if "celery" in dep_lower or "rq " in dep_lower or "queue" in dep_lower or "worker" in dep_lower:
        return "task_queue"
    
    if "redis" in dep_lower or "cache" in dep_lower:
        return "cache_broker"
    
    if "pydantic" in dep_lower:
        return "validation"
    
    if "dotenv" in dep_lower or "config" in dep_lower or "settings" in dep_lower:
        return "config"
    
    if "uvicorn" in dep_lower or "gunicorn" in dep_lower or "hypercorn" in dep_lower:
        return "runtime_server"
    
    if "httpx" in dep_lower or "requests" in dep_lower or "aiohttp" in dep_lower:
        return "http_client"
    
    if "boto" in dep_lower or "aws" in dep_lower or "gcp" in dep_lower or "azure" in dep_lower:
        return "cloud_sdk"
    
    if "fastapi" in dep_lower or "flask" in dep_lower or "django" in dep_lower or "express" in dep_lower:
        return "api_framework"
    
    if "passlib" in dep_lower or "jwt" in dep_lower or "auth" in dep_lower or "oauth" in dep_lower:
        return "auth"
    
    if "jinja" in dep_lower or "template" in dep_lower:
        return "templating"
    
    if "sentry" in dep_lower or "log" in dep_lower or "tracing" in dep_lower or "metrics" in dep_lower:
        return "observability"
    
    return "application_dependency"

CLOUDS = {
    "aws": "AWS",
    "amazon-web-services": "AWS",
    "gcp": "Google Cloud",
    "google-cloud": "Google Cloud",
    "azure": "Azure",
    "heroku": "Heroku",
    "vercel": "Vercel",
    "netlify": "Netlify",
    "cloudflare": "Cloudflare",
    "digitalocean": "DigitalOcean",
}

def parse_requirements_txt(content: str) -> Dict[str, Any]:
    """Parse requirements.txt content."""
    deps = []
    frameworks = []
    databases = []
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        
        pkg = re.split(r"[<>=!~]", line)[0].strip().lower()
        if not pkg:
            continue
        
        deps.append(pkg)
        
        if pkg in PYTHON_FRAMEWORKS:
            frameworks.append(PYTHON_FRAMEWORKS[pkg])
        if pkg in DATABASES:
            databases.append(DATABASES[pkg])
    
    # Classify dependencies by role
    deps_with_roles = []
    for dep in deps:
        deps_with_roles.append({
            "name": dep,
            "role": classify_dependency(dep)
        })
    
    return {
        "dependencies": deps_with_roles,
        "frameworks": list(set(frameworks)),
        "databases": list(set(databases)),
    }


def parse_pyproject_toml(content: str) -> Dict[str, Any]:
    """Parse pyproject.toml content (basic TOML parsing)."""
    deps = []
    frameworks = []
    databases = []
    project_name = ""
    description = ""
    
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {"dependencies": deps, "frameworks": frameworks, "databases": databases}
    
    try:
        data = tomllib.loads(content)
    except Exception:
        return {"dependencies": deps, "frameworks": frameworks, "databases": databases}
    
    project = data.get("project", {})
    project_name = project.get("name", "")
    description = project.get("description", "")
    
    for dep_list in ["dependencies", "optional-dependencies"]:
        if dep_list in project:
            dep_data = project[dep_list]
            if isinstance(dep_data, list):
                for pkg in dep_data:
                    pkg_name = re.split(r"[<>=!~]", pkg)[0].strip().lower()
                    deps.append(pkg_name)
                    if pkg_name in PYTHON_FRAMEWORKS:
                        frameworks.append(PYTHON_FRAMEWORKS[pkg_name])
                    if pkg_name in DATABASES:
                        databases.append(DATABASES[pkg_name])
            elif isinstance(dep_data, dict):
                for group, pkgs in dep_data.items():
                    for pkg in pkgs:
                        pkg_name = re.split(r"[<>=!~]", pkg)[0].strip().lower()
                        deps.append(pkg_name)
                        if pkg_name in PYTHON_FRAMEWORKS:
                            frameworks.append(PYTHON_FRAMEWORKS[pkg_name])
                        if pkg_name in DATABASES:
                            databases.append(DATABASES[pkg_name])
    
    build_system = data.get("build-system", {})
    if build_system.get("requires"):
        for req in build_system["requires"]:
            req_name = re.split(r"[<>=!~]", req)[0].strip().lower()
            if req_name in PYTHON_FRAMEWORKS:
                frameworks.append(PYTHON_FRAMEWORKS[req_name])
    
    # Classify dependencies by role
    deps_with_roles = []
    for dep in deps:
        deps_with_roles.append({
            "name": dep,
            "role": classify_dependency(dep)
        })
    
    return {
        "project_name": project_name,
        "description": description,
        "dependencies": deps_with_roles,
        "frameworks": list(set(frameworks)),
        "databases": list(set(databases)),
    }


def parse_package_json(content: str) -> Dict[str, Any]:
    """Parse package.json content."""
    deps = []
    frameworks = []
    databases = []
    project_name = ""
    description = ""
    scripts = {}
    is_workspace = False
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"dependencies": deps, "frameworks": frameworks, "databases": databases}
    
    project_name = data.get("name", "")
    description = data.get("description", "")
    scripts = data.get("scripts", {})
    
    for dep_list in ["dependencies", "devDependencies", "peerDependencies"]:
        if dep_list in data:
            for pkg in data[dep_list]:
                pkg_name = pkg.lower()
                deps.append(pkg_name)
                if pkg_name in JS_FRAMEWORKS:
                    frameworks.append(JS_FRAMEWORKS[pkg_name])
                if pkg_name in DATABASES:
                    databases.append(DATABASES[pkg_name])
    
    is_workspace = "workspaces" in data or data.get("private") is True
    
    # Classify dependencies by role
    deps_with_roles = []
    for dep in deps:
        deps_with_roles.append({
            "name": dep,
            "role": classify_dependency(dep)
        })
    
    return {
        "project_name": project_name,
        "description": description,
        "scripts": scripts,
        "dependencies": deps_with_roles,
        "frameworks": list(set(frameworks)),
        "databases": list(set(databases)),
        "is_workspace": is_workspace,
    }


def parse_docker_compose(content: str) -> Dict[str, Any]:
    """Parse docker-compose.yml content."""
    services = []
    volumes = []
    networks = []
    ports = []
    
    try:
        import yaml
        data = yaml.safe_load(content)
    except Exception:
        return {"services": services, "volumes": volumes, "networks": networks}
    
    if not isinstance(data, dict):
        return {"services": services, "volumes": volumes, "networks": networks}
    
    if "services" in data:
        for svc_name, svc_config in data["services"].items():
            services.append(svc_name)
            if isinstance(svc_config, dict):
                if "ports" in svc_config:
                    ports.extend(svc_config["ports"])
                if "volumes" in svc_config:
                    for vol in svc_config["volumes"]:
                        if isinstance(vol, str):
                            host_vol = vol.split(":")[0]
                            if not host_vol.startswith("/") and not host_vol.startswith("."):
                                volumes.append(host_vol)
    
    if "volumes" in data:
        for vol in data["volumes"]:
            if isinstance(vol, str):
                volumes.append(vol.split(":")[0])
    
    if "networks" in data:
        networks = list(data["networks"].keys())
    
    return {
        "services": services,
        "volumes": volumes,
        "networks": networks,
        "ports": ports,
    }


def parse_dockerfile(content: str) -> Dict[str, Any]:
    """Parse Dockerfile content."""
    base_image = ""
    exposed_ports = []
    env_vars = []
    volumes = []
    commands = []
    user = ""
    workdir = ""
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        cmd, _, arg = line.partition(" ")
        cmd = cmd.upper()
        commands.append(cmd)
        
        if cmd == "FROM":
            base_image = arg.split()[0] if arg else ""
        elif cmd == "EXPOSE":
            if arg:
                exposed_ports.extend(arg.split())
        elif cmd == "ENV":
            env_vars.append(arg)
        elif cmd == "VOLUME":
            volumes.append(arg)
        elif cmd == "USER":
            user = arg
        elif cmd == "WORKDIR":
            workdir = arg
    
    return {
        "base_image": base_image,
        "exposed_ports": exposed_ports,
        "env_vars": env_vars,
        "volumes": volumes,
        "commands": commands,
        "user": user,
        "workdir": workdir,
    }


def parse_env_example(content: str) -> Dict[str, Any]:
    """Parse .env.example content."""
    env_vars = []
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        key = line.split("=")[0].strip()
        if key:
            env_vars.append(key)
    
    inferred_vars = {
        "database": ["DATABASE_URL", "DB_", "POSTGRES_", "MYSQL_"],
        "redis": ["REDIS_", "CACHE_"],
        "auth": ["AUTH_", "JWT_", "OAUTH_", "SECRET_", "API_KEY"],
        "s3": ["S3_", "AWS_", "STORAGE_"],
        "email": ["MAIL_", "EMAIL_", "SMTP_"],
        "queue": ["QUEUE_", "RABBITMQ_", "CELERY_"],
    }
    
    categories = {}
    for cat, prefixes in inferred_vars.items():
        for var in env_vars:
            if any(var.startswith(p) for p in prefixes):
                categories.setdefault(cat, []).append(var)
    
    return {
        "env_vars": env_vars,
        "inferred_categories": categories,
    }


def parse_makefile(content: str) -> Dict[str, Any]:
    """Parse Makefile content."""
    targets = []
    variables = {}
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if ":" in line and not line.startswith(" "):
            target = line.split(":")[0].strip()
            if target and target.isidentifier() or target.replace("-", "").replace("_", "").isalnum():
                targets.append(target)
        
        if "=" in line and not line.startswith("\t") and not line.startswith(" "):
            var, _, val = line.partition("=")
            if var.strip():
                variables[var.strip()] = val.strip()
    
    common_commands = {
        "run": ["run", "serve", "start", "dev"],
        "test": ["test", "coverage", "pytest"],
        "build": ["build", "compile", "bundle"],
        "lint": ["lint", "format", "check"],
        "migrate": ["migrate", "db", "alembic"],
        "docker": ["docker", "compose", "container"],
        "install": ["install", "deps", "requirements"],
    }
    
    inferred = {}
    for cat, keywords in common_commands.items():
        for target in targets:
            if any(kw in target.lower() for kw in keywords):
                inferred.setdefault(cat, []).append(target)
    
    return {
        "targets": targets,
        "variables": variables,
        "inferred_commands": inferred,
    }


def parse_readme(content: str) -> Dict[str, Any]:
    """Parse README.md content."""
    lines = content.splitlines()
    title = ""
    sections = []
    code_blocks = 0
    
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("#"):
            title = line.lstrip("#").strip()
        
        if line.startswith("##"):
            sections.append(line.lstrip("#").strip())
        
        if line.startswith("```"):
            code_blocks += 1
    
    first_para = ""
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            first_para = line
            break
    
    return {
        "title": title,
        "sections": sections,
        "first_paragraph": first_para,
        "has_code_examples": code_blocks > 0,
    }


def read_file_safe(path: str) -> Optional[str]:
    """Safely read a file, returning None on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None
