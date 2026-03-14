"""Markdown serializer producing real content from extracted context."""
from typing import Dict, Any


def render_overview(context: Dict) -> str:
    """Generate 01-overview.md from context."""
    project_name = context.get("project_name", "Unknown Project")
    summary = context.get("summary", "No summary available.")
    project_type = context.get("project_type", "unknown")
    stack = context.get("stack", {})
    
    lines = [
        f"# {project_name}",
        "",
        f"**Type:** {project_type}",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]
    
    languages = stack.get("languages", [])
    if languages:
        lines.append("## Languages")
        lines.append("")
        for lang in languages:
            lines.append(f"- {lang}")
        lines.append("")
    
    frameworks = stack.get("frameworks", [])
    if frameworks:
        lines.append("## Frameworks")
        lines.append("")
        for fw in frameworks:
            lines.append(f"- {fw}")
        lines.append("")
    
    return "\n".join(lines)


def render_stack(context: Dict) -> str:
    """Generate 02-stack.md from context."""
    stack = context.get("stack", {})
    
    lines = [
        "# Technology Stack",
        "",
    ]
    
    languages = stack.get("languages", [])
    if languages:
        lines.append("## Languages")
        lines.append("")
        for lang in languages:
            lines.append(f"- {lang}")
        lines.append("")
    
    frameworks = stack.get("frameworks", [])
    if frameworks:
        lines.append("## Frameworks")
        lines.append("")
        for fw in frameworks:
            lines.append(f"- {fw}")
        lines.append("")
    
    databases = stack.get("databases", [])
    if databases:
        lines.append("## Databases & Storage")
        lines.append("")
        for db in databases:
            lines.append(f"- {db}")
        lines.append("")
    
    infrastructure = stack.get("infrastructure", [])
    if infrastructure:
        lines.append("## Infrastructure")
        lines.append("")
        for infra in infrastructure:
            lines.append(f"- {infra}")
        lines.append("")
    
    external_services = stack.get("external_services", [])
    if external_services:
        lines.append("## External Services")
        lines.append("")
        for svc in external_services:
            lines.append(f"- {svc}")
        lines.append("")
    
    if not any([languages, frameworks, databases, infrastructure, external_services]):
        lines.append("*No stack information detected.*")
    
    return "\n".join(lines)


def render_components(context: Dict) -> str:
    """Generate 03-components.md from context."""
    components = context.get("components", [])
    
    lines = [
        "# Components",
        "",
    ]
    
    if not components:
        lines.append("*No components detected.*")
        return "\n".join(lines)
    
    type_groups = {}
    for comp in components:
        comp_type = comp.get("type", "unknown")
        type_groups.setdefault(comp_type, []).append(comp)
    
    for comp_type, comps in type_groups.items():
        lines.append(f"## {comp_type.title()}")
        lines.append("")
        for comp in comps:
            name = comp.get("name", "unnamed")
            desc = comp.get("description", "")
            tech = comp.get("tech", [])
            
            lines.append(f"### {name}")
            if desc:
                lines.append(desc)
                lines.append("")
            if tech:
                lines.append(f"**Technologies:** {', '.join(tech)}")
                lines.append("")
    
    return "\n".join(lines)


def render_dependencies(context: Dict) -> str:
    """Generate 04-dependencies.md from context."""
    dependencies = context.get("dependencies", [])
    
    lines = [
        "# Dependencies",
        "",
    ]
    
    if not dependencies:
        lines.append("*No external dependencies detected.*")
        return "\n".join(lines)
    
    type_groups = {}
    for dep in dependencies:
        dep_type = dep.get("type", "unknown")
        type_groups.setdefault(dep_type, []).append(dep)
    
    for dep_type, deps in type_groups.items():
        lines.append(f"## {dep_type}")
        lines.append("")
        for dep in deps:
            name = dep.get("name", "unnamed")
            role = dep.get("role", "")
            conf = dep.get("confidence", 0)
            
            conf_str = f"({int(conf*100)}% confidence)" if conf else ""
            role_str = f" - {role}" if role else ""
            lines.append(f"- {name} {role_str} {conf_str}")
        lines.append("")
    
    return "\n".join(lines)


def render_flows(context: Dict) -> str:
    """Generate 05-flows.md from context."""
    flows = context.get("flows", [])
    
    lines = [
        "# Flows",
        "",
    ]
    
    if not flows:
        lines.append("*No flows detected.*")
        return "\n".join(lines)
    
    for flow in flows:
        name = flow.get("name", "unnamed")
        source = flow.get("source", "?")
        target = flow.get("target", "?")
        desc = flow.get("description", "")
        conf = flow.get("confidence", 0)
        
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"**From:** {source} → **To:** {target}")
        if desc:
            lines.append("")
            lines.append(desc)
        lines.append(f"")
        lines.append(f"*Confidence:* {int(conf*100)}%")
        lines.append("")
    
    return "\n".join(lines)


def render_assumptions(context: Dict) -> str:
    """Generate 06-assumptions.md from context."""
    assumptions = context.get("assumptions", [])
    
    lines = [
        "# Assumptions",
        "",
    ]
    
    if not assumptions:
        lines.append("*No assumptions recorded.*")
        return "\n".join(lines)
    
    for i, assumption in enumerate(assumptions, 1):
        lines.append(f"{i}. {assumption}")
    
    lines.append("")
    return "\n".join(lines)


def render_open_questions(context: Dict) -> str:
    """Generate 07-open-questions.md from context."""
    open_questions = context.get("open_questions", [])
    uncertainties = context.get("uncertainties", [])
    
    lines = [
        "# Open Questions",
        "",
    ]
    
    if not open_questions and not uncertainties:
        lines.append("*No open questions identified.*")
        return "\n".join(lines)
    
    if open_questions:
        lines.append("## Questions")
        lines.append("")
        for i, q in enumerate(open_questions, 1):
            lines.append(f"{i}. {q}")
        lines.append("")
    
    if uncertainties:
        lines.append("## Uncertainties")
        lines.append("")
        for i, u in enumerate(uncertainties, 1):
            lines.append(f"{i}. {u}")
        lines.append("")
    
    return "\n".join(lines)


def render_all(context: Dict) -> Dict[str, str]:
    """Generate all markdown artifacts from context."""
    return {
        "01-overview.md": render_overview(context),
        "02-stack.md": render_stack(context),
        "03-components.md": render_components(context),
        "04-dependencies.md": render_dependencies(context),
        "05-flows.md": render_flows(context),
        "06-assumptions.md": render_assumptions(context),
        "07-open-questions.md": render_open_questions(context),
    }
