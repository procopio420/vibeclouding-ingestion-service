"""Stable question intent keys for phase 1 discovery - pt-BR.

These questions are used internally but should be translated to natural 
Portuguese before showing to users via NaturalLanguageMapper.
"""

from typing import Dict

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
        "question": "O que seu projeto faz? Pode me contar que problema ele resolve?",
        "priority": "high",
        "dependencies": [],
        "phase": "early",
    },
    "q_target_users": {
        "checklist_key": "target_users",
        "question": "Quem são as pessoas que vão usar esse sistema?",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "early",
    },
    "q_entry_channels": {
        "checklist_key": "entry_channels",
        "question": "Como as pessoas vão acessar o sistema? Pelo celular, pelo computador, WhatsApp, ou de outro jeito?",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_application_type": {
        "checklist_key": "application_type",
        "question": "Que tipo de aplicação você está construindo?",
        "priority": "high",
        "dependencies": ["q_product_goal"],
        "phase": "discovery",
    },
    "q_core_components": {
        "checklist_key": "core_components",
        "question": "Quais partes principais esse sistema precisa ter para funcionar bem no dia a dia?",
        "priority": "medium",
        "dependencies": ["q_product_goal", "q_application_type"],
        "phase": "discovery",
    },
    "q_database": {
        "checklist_key": "database",
        "question": "O sistema precisa guardar informações? Que tipo de dados?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_auth_model": {
        "checklist_key": "auth_model",
        "question": "As pessoas precisam fazer login? Cada usuário tem sua própria conta?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "tech",
    },
    "q_external_integrations": {
        "checklist_key": "external_integrations",
        "question": "O sistema vai se conectar com serviços externos? Como WhatsApp, pagamentos, email, mapas?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_file_storage": {
        "checklist_key": "file_storage",
        "question": "O sistema precisa guardar arquivos ou imagens? Como fotos de produtos, documentos, relatórios?",
        "priority": "medium",
        "dependencies": ["q_product_goal"],
        "phase": "tech",
    },
    "q_cache_or_queue": {
        "checklist_key": "cache_or_queue",
        "question": "Você precisa de velocidade extra em alguma parte? Ou algo que rode em segundo plano?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_background_processing": {
        "checklist_key": "background_processing",
        "question": "Vai ter algo rodando automaticamente, sem o usuário precisar acionar?",
        "priority": "medium",
        "dependencies": ["q_application_type"],
        "phase": "tech",
    },
    "q_traffic_expectation": {
        "checklist_key": "traffic_expectation",
        "question": "Quantas pessoas vão usar o sistema? Muita gente logo no início ou vai começar devagar?",
        "priority": "medium",
        "dependencies": ["q_target_users"],
        "phase": "scale",
    },
    "q_availability_requirement": {
        "checklist_key": "availability_requirement",
        "question": "Se o sistema ficar fora do ar por alguns minutos, isso é um problema grande?",
        "priority": "low",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_cost_priority": {
        "checklist_key": "cost_priority",
        "question": "O que é mais importante agora: manter o custo baixo ou já construir algo que possa escalar?",
        "priority": "medium",
        "dependencies": ["q_traffic_expectation"],
        "phase": "scale",
    },
    "q_compliance_or_sensitive_data": {
        "checklist_key": "compliance_or_sensitive_data",
        "question": "Tem algum dado mais sensível nisso? Como documentos, informações financeiras ou dados pessoais?",
        "priority": "low",
        "dependencies": ["q_product_goal"],
        "phase": "security",
    },
}

CHECKLIST_KEYS = [v["checklist_key"] for v in QUESTION_INTENTS.values()]

__all__ = ["QUESTION_INTENTS", "CHECKLIST_KEYS"]
