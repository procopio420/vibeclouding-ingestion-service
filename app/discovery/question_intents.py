"""Stable question intent keys for phase 1 discovery - pt-BR."""

from typing import Dict

# Each intent maps to a stable checklist key and metadata used by the orchestrator
QUESTION_INTENTS: Dict[str, Dict[str, object]] = {
    "q_repo_exists": {
        "checklist_key": "repo_exists",
        "question": "Você já tem um repositório no GitHub para este projeto?",
        "priority": "high",
        "dependencies": [],
        "phase": "early",
    },
    "q_product_goal": {
        "checklist_key": "product_goal",
        "question": "O que seu projeto faz? Pode descrever qual problema ele resolve?",
        "priority": "high",
        "dependencies": [],
        "phase": "early",
    },
    "q_target_users": {
        "checklist_key": "target_users",
        "question": "Quem são os usuários alvo?",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "early",
    },
    "q_entry_channels": {
        "checklist_key": "entry_channels",
        "question": "Como você espera que os usuários acessem o app? (web, mobile, API, WhatsApp, etc.)",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_application_type": {
        "checklist_key": "application_type",
        "question": "Que tipo de aplicação você está construindo? (web app, mobile, API, chatbot, etc.)",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_core_components": {
        "checklist_key": "core_components",
        "question": "Quais são os principais componentes ou funcionalidades do seu aplicativo?",
        "priority": "medium",
        "dependencies": ["q_product_goal", "q_application_type"],
        "phase": "discovery",
    },
    "q_database": {
        "checklist_key": "database",
        "question": "Você vai precisar armazenar dados em um banco de dados? Se sim, que tipo de dados?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_auth_model": {
        "checklist_key": "auth_model",
        "question": "Os usuários vão precisar fazer login? Qual método de autenticação?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "tech",
    },
    "q_external_integrations": {
        "checklist_key": "external_integrations",
        "question": "Vai conectar com APIs externas como WhatsApp, pagamentos, mapas ou email?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_file_storage": {
        "checklist_key": "file_storage",
        "question": "Você vai precisar armazenar arquivos, imagens ou documentos?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_cache_or_queue": {
        "checklist_key": "cache_or_queue",
        "question": "Você vai precisar de cache para performance ou filas de mensagens para processamento em background?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_background_processing": {
        "checklist_key": "background_processing",
        "question": "O app vai precisar processar coisas em background?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_traffic_expectation": {
        "checklist_key": "traffic_expectation",
        "question": "Quantos usuários você espera inicialmente? É um protótipo rápido ou algo que precisa escalar?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "scale",
    },
    "q_availability_requirement": {
        "checklist_key": "availability_requirement",
        "question": "É aceitável o app ficar fora do ar por alguns minutos, ou precisa de alta disponibilidade?",
        "priority": "low",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_cost_priority": {
        "checklist_key": "cost_priority",
        "question": "O que é mais importante agora - manter custos baixos ou construir para escalar?",
        "priority": "medium",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_compliance_or_sensitive_data": {
        "checklist_key": "compliance_or_sensitive_data",
        "question": "Seu aplicativo lida com dados sensíveis ou tem requisitos de conformidade?",
        "priority": "low",
        "dependencies": ["q_product_goal"],
        "phase": "security",
    },
}

from typing import List
CHECKLIST_KEYS = [v["checklist_key"] for v in QUESTION_INTENTS.values()]

__all__ = ["QUESTION_INTENTS", "CHECKLIST_KEYS"]
