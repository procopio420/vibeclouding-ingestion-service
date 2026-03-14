"""Graph DSL serializer producing real content from extracted context."""
from typing import Dict, Any


def serialize_system_graph_dsl(context: Dict = None) -> str:
    """Generate system_graph.dsl from context."""
    if context is None:
        context = {}
    
    components = context.get("components", [])
    stack = context.get("stack", {})
    
    lines = [
        "// system_graph.dsl - Generated from repo analysis",
        "// Version: 1",
        "",
    ]
    
    type_groups = {}
    for comp in components:
        comp_type = comp.get("type", "unknown")
        type_groups.setdefault(comp_type, []).append(comp)
    
    for comp_type, comps in type_groups.items():
        lines.append(f"group {comp_type} {{")
        for comp in comps:
            name = comp.get("name", "unknown")
            desc = comp.get("description", "") or ""
            tech = comp.get("tech", [])
            
            tech_str = f" // {', '.join(tech)}" if tech else ""
            lines.append(f"  node {name} \"{name}\"{tech_str}")
        lines.append("}")
        lines.append("")
    
    infra = stack.get("infrastructure", [])
    if infra:
        lines.append("// Infrastructure")
        for inf in infra:
            lines.append(f"node infra_{inf.replace(' ', '_').lower()} \"{inf}\"")
        lines.append("")
    
    return "\n".join(lines)


def serialize_flow_graph_dsl(context: Dict = None) -> str:
    """Generate flow_graph.dsl from context."""
    if context is None:
        context = {}
    
    flows = context.get("flows", [])
    components = context.get("components", [])
    
    lines = [
        "// flow_graph.dsl - Generated from repo analysis",
        "// Version: 1",
        "",
    ]
    
    component_names = {comp.get("name") for comp in components}
    
    for flow in flows:
        source = flow.get("source", "")
        target = flow.get("target", "")
        flow_type = flow.get("flow_type", "http")
        desc = flow.get("description", "") or ""
        
        if source and target:
            lines.append(f"// {desc}")
            lines.append(f"flow {source} -> {target} \"{flow_type}\"")
            lines.append("")
    
    if not flows:
        lines.append("// No flows detected")
        lines.append("")
    
    return "\n".join(lines)
