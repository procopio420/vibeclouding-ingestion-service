"""Graph artifact generation orchestrator (Phase 1 skeleton)."""
from typing import Dict

from app.serializers.graph_json_serializer import (
    serialize_system_graph,
    serialize_flow_graph,
    serialize_deployment_hints,
)
from app.serializers.graph_dsl_serializer import (
    serialize_system_graph_dsl,
    serialize_flow_graph_dsl,
)


def generate_graph_artifacts(context: Dict = None) -> Dict[str, object]:
    system_json = serialize_system_graph(context)
    flow_json = serialize_flow_graph(context)
    deployment_json = serialize_deployment_hints(context)
    system_dsl = serialize_system_graph_dsl(context)
    flow_dsl = serialize_flow_graph_dsl(context)

    return {
        "system_graph.json": system_json,
        "flow_graph.json": flow_json,
        "deployment_hints.json": deployment_json,
        "system_graph.dsl": system_dsl,
        "flow_graph.dsl": flow_dsl,
    }
