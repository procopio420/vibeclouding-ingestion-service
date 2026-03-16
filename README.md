# VibeCloud Ingestor

API de ingestão de repositórios, descoberta guiada e geração de contexto para definição de arquitetura (VibeCloud).

## O que é este projeto

O **VibeCloud Ingestor** é um serviço backend que:

- **Ingere repositórios** (Git): clona, analisa código e metadados (README, Dockerfile, dependências, etc.) e normaliza em um modelo canônico.
- **Descoberta guiada**: conduz uma sessão de perguntas e respostas (REST + WebSocket) para capturar objetivo do produto, usuários-alvo, stack e requisitos, com checklist e estado de “prontidão”.
- **Gera contexto consolidado**: monta um pacote de contexto (JSON, Markdown, grafos) usado por outros serviços (ex.: gerador de Terraform, agente de arquitetura).
- **Integra com workers**: enfileira jobs de ingestão via Celery (Redis) e persiste artefatos em Postgres e storage (local, R2 ou MinIO).

### Fluxo principal

1. Criar **projeto** (nome, resumo).
2. Iniciar **descoberta** (sessão por projeto): perguntas, respostas, checklist, prontidão.
3. Disparar **ingestão do repositório** (URL do repo); o worker clona, analisa e gera artefatos (contexto, markdown, grafos).
4. Consultar **contexto consolidado** e **próximo passo** para a UI.
5. (Opcional) Solicitar **análise de arquitetura** (vibe econômica vs performance) e notificar o gerador Terraform.

---

## Stack e tecnologias

| Área           | Tecnologia |
|----------------|------------|
| **Backend**   | Python 3.11+, FastAPI |
| **Banco**     | PostgreSQL 15 |
| **Filas**     | Celery, Redis (broker e result backend) |
| **Storage**   | Local, Cloudflare R2 ou MinIO (S3-compatível) |
| **Migrações** | Alembic |
| **LLM (opcional)** | Gemini ou OpenAI para enriquecimento de análise |
| **Infra**     | Docker, Docker Compose |

Integrações relevantes:

- **Terraform Generator**: webhook/notificação ao definir decisão de revisão (`vibe_economica` / `vibe_performance`).
- **Webhook opcional**: notificação quando o contexto consolidado é gerado.

---

## Equipe / Membros

| Nome   | Função        | Contato (opcional) |
|--------|----------------|--------------------|
| *Lucsa Procopio* | *Software Engineer* | [GitHub](https://github.com/procopio420/) / [LinkedIn](https://www.linkedin.com/in/lucas-procopio/) |
| *Laisa Rio* | *Software Engineer* | [GitHub](https://github.com/laisario/) / [LinkedIn](https://www.linkedin.com/in/laisa-rio/) |
| *Paulo Boccaletti* | *Tech Leader* | [GitHub](https://github.com/pboccaletti) / [LinkedIn](https://www.linkedin.com/in/pauloboccaletti/) |

---

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Docker e Docker Compose (para Postgres e Redis)
- Git

### Ambiente

1. Clone o repositório e entre na pasta do projeto:

   ```bash
   git clone <url-do-repo>
   cd ingestor
   ```

2. Crie um ambiente virtual e instale as dependências:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   # ou: .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. Copie o arquivo de exemplo de variáveis de ambiente e ajuste:

   ```bash
   cp .env.example .env
   ```

   No mínimo, configure para desenvolvimento local:

   - `DATABASE_URL=postgresql://vibe:vibe@localhost:5432/vibe_context`
   - `CELERY_BROKER_URL=redis://localhost:6379/0`
   - `STORAGE_BACKEND=local` (e opcionalmente `LOCAL_STORAGE_PATH=./artifacts`)

### Banco de dados e Redis

Com Docker Compose (apenas `db` e `redis`):

```bash
docker compose up -d db redis
```

Aplicar migrações (na primeira vez ou após pull):

```bash
python -m alembic upgrade head
```

### Backend (API)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará em `http://localhost:8000`. Documentação interativa: `http://localhost:8000/docs`.

### Worker (Celery)

Em outro terminal, com o mesmo ambiente ativado:

```bash
celery -A app.celery_app worker --loglevel=info -Q repo_ingest
```

### Frontend

Este repositório contém apenas o **backend**. O frontend da descoberta (ex.: React em outra URL) consome a API e o WebSocket do Ingestor. Configure a origem no CORS (já há `localhost:8081` e `localhost:3000` no código).

---

## Como usar

### Desenvolvedor / testador

1. **Criar projeto**: `POST /projects` com `name` e opcionalmente `summary`.
2. **Listar projetos**: `GET /projects` (retorna IDs e `repo_url` quando houver).
3. **Iniciar descoberta**: usar os endpoints em `docs/API_DISCOVERY.md` (sessão, perguntas, respostas, checklist).
4. **Disparar ingestão**: `POST /projects/{project_id}/ingest` com `repo_url` e opcionalmente `reference` (branch).
5. **Consultar contexto**: `GET /projects/{project_id}/context` (contexto consolidado + `understanding_summary` + `next_best_step`).
6. **Atividade**: `GET /projects/{project_id}/activity` (feed de eventos da descoberta).
7. **Decisão de revisão**: `PUT /projects/{project_id}/revision-decision` com `decision: "vibe_economica"` ou `"vibe_performance"` (aciona notificação ao Terraform Generator se configurado).

WebSocket de descoberta: conectar em `/ws/discovery?project_id=...&client_id=...` para chat e eventos em tempo real.

### Endpoints principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Health / status |
| GET/POST | `/projects` | Listar / criar projetos |
| GET | `/projects/{id}/context` | Contexto consolidado + resumo + próximo passo |
| GET | `/projects/{id}/activity` | Feed de atividade |
| POST | `/projects/{id}/ingest` | Enfileirar ingestão do repositório |
| PUT | `/projects/{id}/revision-decision` | Definir decisão (vibe) e notificar Terraform |
| WebSocket | `/ws/discovery` | Sessão de descoberta (chat e eventos) |

---

## Estrutura do projeto

```
ingestor/
├── app/
│   ├── main.py              # Aplicação FastAPI e rotas
│   ├── db.py                # Modelos SQLAlchemy e sessão
│   ├── celery_app.py        # Celery, tarefa repo_ingest_worker
│   ├── api/
│   │   ├── routes/          # Rotas REST (projects, ingest, discovery, outputs, etc.)
│   │   └── schemas.py       # Schemas Pydantic
│   ├── discovery/           # Descoberta guiada (orquestrador, checklist, perguntas, prontidão)
│   ├── repo_analysis/       # Análise de repositório (parsers, LLM opcional, normalização)
│   ├── pipelines/           # repo_pipeline, graph_pipeline (artefatos)
│   ├── serializers/         # Markdown e grafos (JSON/DSL)
│   ├── services/            # context_aggregator, readiness, webhook, terraform client
│   ├── adapters/            # Storage (local, R2), Git
│   ├── websocket/           # WebSocket descoberta (connection manager, service)
│   ├── events/              # Contratos e publicador de eventos
│   ├── domain/              # Modelos e schemas de domínio
│   └── repositories/        # Persistência de resultados de arquitetura
├── alembic/                 # Migrações do banco
├── tests/                   # Testes
├── docs/                    # Documentação (API, design, changelog)
├── docker-compose.yml       # Postgres, Redis, API, Celery
├── Dockerfile
├── entrypoint.sh            # Migrações + comando do container
├── requirements.txt
├── .env.example
├── LICENSE
└── README.md
```

A pasta `artifacts/` é gerada em tempo de execução (contexto, markdown, grafos por projeto) e não deve ser versionada (está no `.gitignore`).

---

## Licença

Este projeto está sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para o texto completo.

Em resumo: você pode usar, modificar e distribuir o software, desde que o aviso de copyright e a licença sejam mantidos nos cópias.

---

## Documentação adicional

- **docs/API_DISCOVERY.md** — Formato da API de descoberta (contexto, próximo passo, atividade).
- **docs/PHASE1_DESIGN.md** — Visão e escolhas de design da Fase 1.
- **docs/CHANGELOG.md** — Registro de mudanças.
- **docs/MIGRATIONS/** — Guias de migração (ex.: Discovery API Enhancement).

Para contribuir, veja [CONTRIBUTING.md](CONTRIBUTING.md) (se disponível).
