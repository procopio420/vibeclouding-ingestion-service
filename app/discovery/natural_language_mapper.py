"""Natural language mapper for discovery - translates internal keys to user-friendly Portuguese."""

from typing import Dict, Optional, List


class NaturalLanguageMapper:
    """Maps internal checklist keys to natural, user-friendly Portuguese questions."""

    MAPPING: Dict[str, Dict] = {
        "repo_exists": {
            "question": "Você já tem um repositório no GitHub para o projeto?",
            "explanation": None,
            "examples": [],
            "type": "simple",
        },
        "product_goal": {
            "question": "O que seu projeto faz? Pode me contar que problema ele resolve?",
            "explanation": None,
            "examples": [],
            "type": "simple",
        },
        "target_users": {
            "question": "Quem são as pessoas que vão usar esse sistema?",
            "explanation": "Pode ser clientes, funcionários, parceiros, etc.",
            "examples": ["clientes", "funcionários", "parceiros", "fornecedores"],
            "type": "explanation",
        },
        "entry_channels": {
            "question": "Como as pessoas vão acessar o sistema? Pelo celular, pelo computador, WhatsApp, ou de outro jeito?",
            "explanation": "Cada canal tem implicações diferentes para a arquitetura.",
            "examples": ["celular", "computador", "navegador", "WhatsApp", "app nativo"],
            "type": "explanation",
        },
        "application_type": {
            "question": "Que tipo de aplicação você está construindo?",
            "explanation": "Pode ser um site, app de celular, sistema interno, API, chatbot, etc.",
            "examples": ["site", "app mobile", "sistema web", "API", "chatbot", "loja virtual"],
            "type": "explanation",
        },
        "core_components": {
            "question": "Quais partes principais esse sistema precisa ter para funcionar bem no dia a dia?",
            "explanation": "Por exemplo: login e cadastro, gestão de pedidos, painel administrativo, catálogo de produtos, pagamentos, notificações, relatórios...",
            "examples": ["cadastro", "pedidos", "login", "painel admin", "catálogo", "pagamentos", "notificações"],
            "type": "explanation",
        },
        "database": {
            "question": "O sistema precisa guardar informações? Que tipo de dados?",
            "explanation": "Quase todo sistema precisa de banco de dados. Pode ser dados de usuários, produtos, pedidos, logs, etc.",
            "examples": ["usuários", "produtos", "pedidos", "transações", "relatórios"],
            "type": "explanation",
        },
        "auth_model": {
            "question": "As pessoas precisam fazer login? Cada usuário tem sua própria conta?",
            "explanation": "Tipo: produtores e clientes com contas próprias, ou apenas acesso livre?",
            "examples": ["login", "conta própria", "cadastro", "autenticação"],
            "type": "explanation",
        },
        "external_integrations": {
            "question": "O sistema vai se conectar com serviços externos? Como WhatsApp, pagamentos, email, mapas?",
            "explanation": "Integrações comuns: WhatsApp Business, Stripe/pagamentos, SendGrid/email, Google Maps, etc.",
            "examples": ["WhatsApp", "Stripe", "pagamentos", "email", "mapas", " APIs"],
            "type": "explanation",
        },
        "file_storage": {
            "question": "O sistema precisa guardar arquivos ou imagens? Como fotos de produtos, documentos, relatórios em PDF?",
            "explanation": "Pode ser imagens, PDFs, planilhas, backups, etc.",
            "examples": ["fotos", "imagens", "documentos", "PDFs", "anexos"],
            "type": "explanation",
        },
        "cache_or_queue": {
            "question": "Você precisa de velocidade extra em alguma parte? Ou algo que rode em segundo plano?",
            "explanation": "Tipo: cache para deixar o sistema mais rápido, ou filas para processar coisas sem travar a interface.",
            "examples": ["cache", "fila", "performance", "segundo plano"],
            "type": "explanation",
        },
        "background_processing": {
            "question": "Vai ter algo rodando automaticamente, sem o usuário precisar acionar?",
            "explanation": "Como: envio de notificações, geração de relatórios, cálculos de comissão, processamento de pedidos, envios de email em massa, etc.",
            "examples": ["notificações", "relatórios", "cálculos", "processamento automático", "fila"],
            "type": "explanation",
        },
        "traffic_expectation": {
            "question": "Quantas pessoas vão usar o sistema? Muita gente logo no início ou vai começar devagar?",
            "explanation": "Isso ajuda a decidir se precisamos de uma arquitetura que escala muito ou se algo mais simples resolve no começo.",
            "examples": ["muitos usuários", "poucos usuários", "crescimento", "escala"],
            "type": "explanation",
        },
        "availability_requirement": {
            "question": "Se o sistema ficar fora do ar por alguns minutos, isso é um problema grande?",
            "explanation": "Para alguns sistemas tudo bem, para outros (como pagamentos) precisa de alta disponibilidade.",
            "examples": ["alta disponibilidade", " downtime ", " outage "],
            "type": "explanation",
        },
        "cost_priority": {
            "question": "O que é mais importante agora: manter o custo baixo no início ou já construir algo que possa escalar?",
            "explanation": "Às vezes.compensa começar simples e depois evoluir. Outras vezes compensa investir mais no começo para evitar refatoração.",
            "examples": ["custo", "orçamento", "escalar", "barato", "investimento"],
            "type": "explanation",
        },
        "compliance_or_sensitive_data": {
            "question": "Tem algum dado mais sensível nisso? Como documentos, informações financeiras ou dados pessoais?",
            "explanation": "Dados sensíveis exigem mais cuidado com segurança e às vezes têm exigências legais (LGPD, PCI, etc).",
            "examples": ["dados pessoais", "LGPD", "cartão", "CPF", "documentos", "financeiro"],
            "type": "explanation",
        },
        "project_name": {
            "question": "Como você quer chamar esse projeto?",
            "explanation": None,
            "examples": [],
            "type": "simple",
        },
    }

    @classmethod
    def get_question(cls, key: str) -> str:
        """Get the natural question for an internal key."""
        mapping = cls.MAPPING.get(key, {})
        return mapping.get("question", f"Me conte mais sobre {key}")

    @classmethod
    def get_full_question(cls, key: str) -> str:
        """Get the question with explanation if available."""
        mapping = cls.MAPPING.get(key, {})
        question = mapping.get("question", "")
        
        if mapping.get("explanation") and mapping.get("type") == "explanation":
            return f"{question} {mapping['explanation']}"
        
        return question

    @classmethod
    def get_examples(cls, key: str) -> List[str]:
        """Get example terms for an internal key."""
        mapping = cls.MAPPING.get(key, {})
        return mapping.get("examples", [])

    @classmethod
    def has_explanation(cls, key: str) -> bool:
        """Check if key has an explanation."""
        mapping = cls.MAPPING.get(key, {})
        return bool(mapping.get("explanation"))

    @classmethod
    def get_all_keys(cls) -> List[str]:
        """Get all available keys."""
        return list(cls.MAPPING.keys())

    @classmethod
    def is_simple_type(cls, key: str) -> bool:
        """Check if key is a simple (non-explanation) type."""
        mapping = cls.MAPPING.get(key, {})
        return mapping.get("type") == "simple"


__all__ = ["NaturalLanguageMapper"]
