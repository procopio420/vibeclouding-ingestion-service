"""Graph JSON serializer producing real content from extracted context."""
from typing import Dict, Any, List


def serialize_system_graph(context: Dict = None) -> Dict:
    """Generate system_graph.json from context."""
    if context is None:
        context = {}
    
    components = context.get("components", [])
    dependencies = context.get("dependencies", [])
    stack = context.get("stack", {})
    
    nodes = []
    edges = []
    groups = []
    
    component_names = set()
    for comp in components:
        node_id = comp.get("name", "unknown")
        component_names.add(node_id)
        
        node = {
            "id": node_id,
            "label": node_id,
            "type": comp.get("type", "module"),
            "description": comp.get("description", ""),
            "technologies": comp.get("tech", []),
        }
        nodes.append(node)
    
    type_groups = {}
    for comp in components:
        comp_type = comp.get("type", "unknown")
        type_groups.setdefault(comp_type, []).append(comp.get("name"))
    
    for comp_type, names in type_groups.items():
        groups.append({
            "id": comp_type,
            "label": comp_type.title(),
            "nodes": names,
        })
    
    infra = stack.get("infrastructure", [])
    if infra:
        for i, inf in enumerate(infra):
            node_id = f"infra_{i}"
            nodes.append({
                "id": node_id,
                "label": inf,
                "type": "infrastructure",
            })
    
    assumptions = context.get("assumptions", [])
    open_questions = context.get("open_questions", [])
    uncertainties = context.get("uncertainties", [])
    
    return {
        "version": 1,
        "nodes": nodes,
        "edges": edges,
        "groups": groups,
        "assumptions": assumptions,
        "uncertainties": uncertainties,
        "open_questions": open_questions,
    }


def serialize_flow_graph(context: Dict = None) -> Dict:
    """Generate flow_graph.json from context."""
    if context is None:
        context = {}
    
    flows = context.get("flows", [])
    components = context.get("components", [])
    
    flow_edges = []
    nodes = []
    
    component_names = set()
    for comp in components:
        component_names.add(comp.get("name", "unknown"))
    
    for flow in flows:
        source = flow.get("source", "")
        target = flow.get("target", "")
        flow_type = flow.get("flow_type", "http")
        
        if source and target:
            flow_edges.append({
                "source": source,
                "target": target,
                "type": flow_type,
                "label": flow.get("name", ""),
                "description": flow.get("description", ""),
                "confidence": flow.get("confidence", 0),
            })
        
        if source not in component_names:
            nodes.append({"id": source, "label": source, "type": "component"})
        if target not in component_names:
            nodes.append({"id": target, "label": target, "type": "component"})
    
    assumptions = context.get("assumptions", [])
    uncertainties = context.get("uncertainties", [])
    open_questions = context.get("open_questions", [])
    
    return {
        "version": 1,
        "flows": flow_edges,
        "nodes": nodes,
        "edges": flow_edges,
        "assumptions": assumptions,
        "uncertainties": uncertainties,
        "open_questions": open_questions,
    }


def serialize_deployment_hints(context: Dict = None) -> Dict:
    """Generate deployment_hints.json from context - upgraded version."""
    if context is None:
        context = {}
    
    stack = context.get("stack", {})
    components = context.get("components", [])
    dependencies = context.get("dependencies", [])
    flows = context.get("flows", [])
    assumptions = context.get("assumptions", [])
    
    likely_public_services = []
    likely_stateful_services = []
    likely_async_processing = []
    likely_external_services = []
    likely_secrets = []
    likely_file_storage = []
    scaling_sensitive = []
    
    # Component-based inference
    for comp in components:
        comp_type = comp.get("type", "")
        comp_name = comp.get("name", "")
        
        if comp_type in ["api", "frontend", "service"]:
            likely_public_services.append(comp_name)
            if comp_type == "api":
                scaling_sensitive.append({
                    "component": comp_name,
                    "reason": "API handles HTTP traffic - consider horizontal scaling and load balancing"
                })
        
        if comp_type == "database":
            likely_stateful_services.append(comp_name)
            scaling_sensitive.append({
                "component": comp_name,
                "reason": "Database requires persistent storage and careful scaling strategy"
            })
        
        if comp_type == "cache":
            likely_stateful_services.append(comp_name)
            scaling_sensitive.append({
                "component": comp_name,
                "reason": "Cache service - consider Redis Cluster or Sentinel for HA"
            })
        
        if comp_type == "worker":
            likely_async_processing.append(comp_name)
            scaling_sensitive.append({
                "component": comp_name,
                "reason": "Worker processes - can scale horizontally for throughput"
            })
        
        if comp_type == "external_service":
            likely_external_services.append({
                "name": comp_name,
                "type": "external_integration"
            })
    
    # Dependency-based inference
    for dep in dependencies:
        name = dep.get("name", "").lower()
        role = dep.get("role", "")
        
        if "s3" in name or "storage" in name or "minio" in name:
            likely_file_storage.append(name)
        
        if "postgres" in name or "mysql" in name or "mongo" in name:
            if "PostgreSQL" not in likely_stateful_services:
                likely_stateful_services.append("database")
        
        if "redis" in name:
            if "Redis" not in likely_stateful_services:
                likely_stateful_services.append("Redis")
        
        # Secrets inference
        if role == "auth":
            likely_secrets.append({
                "category": "authentication",
                "examples": ["API keys", "OAuth tokens", "JWT secrets"]
            })
        
        if role == "database_driver":
            likely_secrets.append({
                "category": "database",
                "examples": ["DB_HOST", "DB_PASSWORD", "DB_USER"]
            })
    
    # Flow-based inference
    flow_types = set(f.get("flow_type", "") for f in flows)
    if "message" in flow_types:
        for comp in likely_async_processing:
            pass  # Already captured
    
    # Infrastructure
    infra = stack.get("infrastructure", [])
    databases = stack.get("databases", [])
    
    # External services from stack
    external_svcs = stack.get("external_services", [])
    for svc in external_svcs:
        if svc not in likely_external_services:
            likely_external_services.append({"name": svc, "type": "cloud_service"})
    
    # Build comprehensive scaling guidance
    scaling_guidance = {}
    
    if "Docker" in infra or "Docker Compose" in infra:
        scaling_guidance["containerization"] = "Docker detected - suitable for Kubernetes, ECS, or Docker Swarm deployment"
    
    if databases:
        scaling_guidance["database"] = f"Detected databases: {', '.join(databases)}"
    
    if likely_async_processing:
        scaling_guidance["async_jobs"] = f"Background processing: {', '.join(likely_async_processing)}"
        scaling_guidance["worker_scaling"] = "Workers can scale independently from API - consider HPA based on queue depth"
    
    if likely_stateful_services:
        scaling_guidance["stateful_services"] = "Stateful services require careful HA setup - consider managed databases"
    
    if likely_external_services:
        ext_names = [e["name"] if isinstance(e, dict) else e for e in likely_external_services]
        scaling_guidance["external_integrations"] = f"External services: {', '.join(ext_names)}"
    
    # Generate notes
    notes = []
    
    if not likely_public_services:
        notes.append("No clear public-facing services detected - may be internal tool")
    else:
        notes.append(f"Public services: {', '.join(likely_public_services)}")
    
    if not likely_stateful_services:
        notes.append("WARNING: No stateful services detected - verify data persistence strategy")
    else:
        notes.append(f"Stateful services: {', '.join(likely_stateful_services)}")
    
    if likely_async_processing:
        notes.append(f"Async processing: {', '.join(likely_async_processing)} - consider monitoring queue depth")
    
    if likely_external_services:
        ext_names = [e["name"] if isinstance(e, dict) else e for e in likely_external_services]
        notes.append(f"External integrations: {', '.join(ext_names)}")
    
    if not infra:
        notes.append("Limited containerization - may need manual deployment setup")
    
    if assumptions:
        notes.append(f"Key assumptions: {assumptions[0]}")
    
    # Build comprehensive output
    result = {
        "version": 1,
        "likely_public_services": likely_public_services,
        "likely_stateful_services": likely_stateful_services,
        "likely_async_processing": likely_async_processing,
        "likely_external_services": likely_external_services,
        "likely_file_storage": likely_file_storage,
        "likely_secrets": likely_secrets if likely_secrets else [
            {"category": "general", "examples": ["SECRET_KEY", "API_KEYS", "DATABASE_URL"]}
        ],
        "scaling_sensitive_components": scaling_sensitive,
        "scaling_guidance": scaling_guidance,
        "notes": notes if notes else ["Analysis complete - review components for deployment"],
    }
    
    return result
