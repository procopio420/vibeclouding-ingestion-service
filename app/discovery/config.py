"""Language configuration for discovery flow - pt-BR enforcement."""

# User-facing language policy
USER_LANGUAGE = "pt-BR"

# pt-BR Bootstrap questions (initial conversation)
BOOTSTRAP_QUESTIONS_PT = [
    "O que seu projeto faz? Pode descrever qual problema ele resolve?",
    "Você já tem um repositório no GitHub para ele?",
    "Tem alguma documentação, diagrama ou notas?",
    "O que é mais importante agora: menor custo ou melhor performance?",
]

# pt-BR Fallback messages
FALLBACK_MESSAGES_PT = {
    "initial": "Olá! Estou aqui para ajudar a definir seu projeto. O que ele faz? Você tem um repositório?",
    "repo_detected": "Obrigado por compartilhar o repositório! Estou analisando agora. Enquanto isso, pode me contar mais sobre o que o projeto faz?",
    "default": "Pode me contar mais sobre seu projeto?",
    "complete": "Entendi! Tenho uma boa visão do seu projeto. Me avise quando quiser prosseguir para a fase de arquitetura.",
}

# pt-BR Readiness notes
NOTES_PT = {
    "missing_critical": "Itens críticos faltando",
    "questions_open": "Perguntas abertas",
    "context_gaps": "GAPs de contexto",
    "repo_complete": "Análise do repositório completa",
    "repo_pending": "Análise do repositório pendente",
}

# Activity event labels (machine key -> pt-BR label for UI)
ACTIVITY_LABELS_PT = {
    "question_open": "Questão em aberto",
    "question_answered": "Questão respondida",
    "repo_ingest": "Carregando repositório",
    "repo_ingest_started": "Carregando repositório",
    "repo_ingest_completed": "Repositório carregado",
}

# Next step descriptions
NEXT_STEP_DESCRIPTIONS_PT = {
    "repo_exists": "Verificar se existe um repositório para o projeto.",
    "product_goal": "Entender o objetivo e propósito do projeto.",
    "target_users": "Identificar quem são os usuários alvo.",
    "entry_channels": "Definir por quais canais os usuários acessarão.",
    "application_type": "Determinar o tipo de aplicação.",
    "core_components": "Mapear os principais componentes e funcionalidades.",
    "database": "Especificar kebutuhan de banco de dados.",
    "auth_model": "Definir modelo de autenticação.",
    "external_integrations": "Identificar integrações externas necessárias.",
    "file_storage": "Especificar necessidades de armazenamento de arquivos.",
    "cache_or_queue": "Determinar uso de cache ou filas.",
    "background_processing": "Mapear processamento em background.",
    "traffic_expectation": "Estimar expectativa de tráfego.",
    "availability_requirement": "Definir requisitos de disponibilidade.",
    "cost_priority": "Estabelecer prioridade entre custo e escala.",
    "compliance_or_sensitive_data": "Verificar requisitos de conformidade.",
}

# Generic next step fallback
NEXT_STEP_FALLBACK = "Próximo passo para "

# Understanding summary labels
UNDERSTANDING_LABELS_PT = {
    "confirmed": "Confirmado",
    "inferred": "Inferido",
}

# Prompt instruction for LLM
LLM_PROMPT_LANGUAGE_INSTRUCTION = """IMPORTANTE: Responda SEMPRE em português brasileiro (pt-BR)."""


__all__ = [
    "USER_LANGUAGE",
    "BOOTSTRAP_QUESTIONS_PT",
    "FALLBACK_MESSAGES_PT",
    "NOTES_PT",
    "ACTIVITY_LABELS_PT",
    "NEXT_STEP_DESCRIPTIONS_PT",
    "NEXT_STEP_FALLBACK",
    "UNDERSTANDING_LABELS_PT",
    "LLM_PROMPT_LANGUAGE_INSTRUCTION",
]
