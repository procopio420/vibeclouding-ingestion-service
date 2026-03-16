# Como contribuir

Obrigado pelo interesse em contribuir com o VibeCloud Ingestor. Abaixo estão orientações para manter o projeto consistente.

## Ambiente de desenvolvimento

1. Siga as instruções do [README.md](README.md) para configurar o ambiente (venv, `.env`, Postgres, Redis).
2. Rode as migrações: `python -m alembic upgrade head`.
3. Execute os testes: `pytest tests/ -v` (requer dependências e, para alguns testes, Redis/Postgres conforme configuração).

## Padrões de código

- **Python**: estilo consistente (ex.: formatação com Black/ruff se adotados pelo projeto).
- **Imports**: evite imports circulares; use imports absolutos a partir de `app`.
- **Tipos**: use type hints onde fizer sentido para APIs e funções públicas.
- **Docstrings**: módulos e funções públicas com docstring breve quando o comportamento não for óbvio.

## Commits e histórico

- Prefira mensagens de commit objetivas e em inglês (ou pt-BR, conforme convenção da equipe).
- Exemplos: `Add endpoint to list projects with repo_url`, `Fix readiness check bool error`.
- Evite commits genéricos como "WIP", "fix", "tmp" ou "random"; use um rebase/squash antes de integrar para manter o histórico limpo.

## Pull requests

- Descreva o que foi alterado e por quê.
- Garanta que os testes existentes passem e que novas funcionalidades tenham cobertura quando fizer sentido.
- Se alterar contrato de API ou variáveis de ambiente, atualize o README e o `.env.example`.

## Dúvidas

Abra uma issue no repositório ou entre em contato com a equipe (ver seção Equipe no README).
