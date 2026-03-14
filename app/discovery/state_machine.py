"""Discovery state machine with explicit transitions."""
from typing import Dict, List, Set, Optional


class DiscoveryStateMachine:
    """Manages discovery state transitions."""
    
    STATES = [
        "idle",
        "collecting_initial_context",
        "ingesting_sources",
        "clarifying_core_requirements",
        "merging_context",
        "needs_user_confirmation",
        "ready_for_architecture",
        "architecture_in_progress",
        "architecture_ready",
        "source_ingestion_failed",
    ]
    
    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        "idle": {"collecting_initial_context"},
        "collecting_initial_context": {"ingesting_sources", "clarifying_core_requirements"},
        "ingesting_sources": {"clarifying_core_requirements", "source_ingestion_failed"},
        "source_ingestion_failed": {"collecting_initial_context", "clarifying_core_requirements"},
        "clarifying_core_requirements": {"merging_context"},
        "merging_context": {"clarifying_core_requirements", "needs_user_confirmation", "ready_for_architecture"},
        "needs_user_confirmation": {"clarifying_core_requirements", "ready_for_architecture"},
        "ready_for_architecture": {"architecture_in_progress"},
        "architecture_in_progress": {"architecture_ready"},
        "architecture_ready": set(),
    }
    
    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """Check if transition from one state to another is valid."""
        if from_state not in cls.VALID_TRANSITIONS:
            return False
        return to_state in cls.VALID_TRANSITIONS[from_state]
    
    @classmethod
    def get_valid_transitions(cls, current_state: str) -> List[str]:
        """Get list of valid transitions from current state."""
        return list(cls.VALID_TRANSITIONS.get(current_state, set()))
    
    @classmethod
    def is_valid_state(cls, state: str) -> bool:
        """Check if a state is valid."""
        return state in cls.STATES
    
    @classmethod
    def get_initial_state(cls) -> str:
        """Get the initial state for new discovery sessions."""
        return "collecting_initial_context"


def get_readiness_from_state(state: str) -> str:
    """Map discovery state to readiness status."""
    mapping = {
        "idle": "not_ready",
        "collecting_initial_context": "not_ready",
        "ingesting_sources": "not_ready",
        "clarifying_core_requirements": "needs_clarification",
        "merging_context": "needs_clarification",
        "needs_user_confirmation": "needs_clarification",
        "ready_for_architecture": "ready_for_architecture",
        "architecture_in_progress": "ready_for_architecture",
        "architecture_ready": "ready_for_architecture",
        "source_ingestion_failed": "not_ready",
    }
    return mapping.get(state, "not_ready")


__all__ = ["DiscoveryStateMachine", "get_readiness_from_state"]
