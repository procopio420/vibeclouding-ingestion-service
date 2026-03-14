"""Stable question intent keys for phase 1 discovery."""

from typing import Dict

# Each intent maps to a stable checklist key and metadata used by the orchestrator
QUESTION_INTENTS: Dict[str, Dict[str, object]] = {
    "q_repo_exists": {
        "checklist_key": "repo_exists",
        "question": "Do you already have a GitHub repo for this project?",
        "priority": "high",
        "dependencies": [],
        "phase": "early",
    },
    "q_product_goal": {
        "checklist_key": "product_goal",
        "question": "What does your project do? Can you describe what problem it solves?",
        "priority": "high",
        "dependencies": [],
        "phase": "early",
    },
    "q_target_users": {
        "checklist_key": "target_users",
        "question": "Who are your target users?",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "early",
    },
    "q_entry_channels": {
        "checklist_key": "entry_channels",
        "question": "How do you expect users to access your app? (web, mobile, API, WhatsApp, etc.)",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_application_type": {
        "checklist_key": "application_type",
        "question": "What type of application are you building? (web app, mobile, API, chatbot, etc.)",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_core_components": {
        "checklist_key": "core_components",
        "question": "What are the main components or features of your application?",
        "priority": "medium",
        "dependencies": ["q_product_goal", "q_application_type"],
        "phase": "discovery",
    },
    "q_database": {
        "checklist_key": "database",
        "question": "Will you need to store data in a database? If so, what kind of data?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_auth_model": {
        "checklist_key": "auth_model",
        "question": "Will users need to log in? What authentication method?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "tech",
    },
    "q_external_integrations": {
        "checklist_key": "external_integrations",
        "question": "Will it connect to external APIs like WhatsApp, payments, maps, or email?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_file_storage": {
        "checklist_key": "file_storage",
        "question": "Will you need to store files, images, or documents?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_cache_or_queue": {
        "checklist_key": "cache_or_queue",
        "question": "Will you need caching for performance or message queues for background processing?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_background_processing": {
        "checklist_key": "background_processing",
        "question": "Will the app need to process things in the background?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_traffic_expectation": {
        "checklist_key": "traffic_expectation",
        "question": "How many users do you expect initially? Is this a quick prototype or something that needs to scale?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "scale",
    },
    "q_availability_requirement": {
        "checklist_key": "availability_requirement",
        "question": "Is it okay if the app goes down for a few minutes, or does it need high availability?",
        "priority": "low",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_cost_priority": {
        "checklist_key": "cost_priority",
        "question": "What's more important right now - keeping costs low or building for scale?",
        "priority": "medium",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_compliance_or_sensitive_data": {
        "checklist_key": "compliance_or_sensitive_data",
        "question": "Does your application handle sensitive data or have compliance requirements?",
        "priority": "low",
        "dependencies": ["q_product_goal"],
        "phase": "security",
    },
}

from typing import List
CHECKLIST_KEYS = [v["checklist_key"] for v in QUESTION_INTENTS.values()]

__all__ = ["QUESTION_INTENTS", "CHECKLIST_KEYS"]
