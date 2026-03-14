Phase 1 Design Document: Ingestion & Normalization (PDD)

Scope
- Build a FastAPI-based microservice that ingests raw project context from multiple sources, normalizes to a canonical model, renders a Context Pack (markdown + diagrams), and exposes this via a clean API.
- Phase 1 focuses on structure, extraction scaffolds, and deterministic normalization, not final architectural decisions or cloud provisioning.

Key choices (aligned with preferences)
- Metadata: Postgres
- Artifacts: MinIO for local/dev; S3-compatible storage for live
- Processing: Celery with Redis as broker; multi-node capable
- Ingestion: Accept multiple artifacts per call; only public repos initially
- Outputs: JSON context payload plus Markdown docs; Mermaid diagrams; inline or separate blocks
- Diagrams: system context + critical-flow diagrams
- Deployment: Containerized via Docker Compose for local/dev; plan for Kubernetes later
- Clarifications: Few high-signal questions persisted in the model and 07-open-questions.md

1) Canonical model (versioned)
Goal: a structured, versioned schema that all pipelines map into. The first version is intentionally minimal but extensible.

Example Pydantic-like model (conceptual):
```json
{
  "version": 1,
  "project_name": "",
  "summary": "",
  "input_sources": [
    {"id": "src1", "type": "image", "source": "https://...", "metadata": {}}
  ],
  "stack": {
    "languages": [],
    "frameworks": [],
    "databases": [],
    "infrastructure": [],
    "external_services": []
  },
  "components": [
    {"name": "", "type": "", "description": "", "responsibilities": [], "tech": [], "depends_on": [], "exposes": [], "consumes": []}
  ],
  "flows": [
    {"name": "", "source": "", "target": "", "description": "", "confidence": 0.0}
  ],
  "dependencies": [
    {"name": "", "type": "", "role": "", "confidence": 0.0}
  ],
  "assumptions": [],
  "open_questions": [],
  "uncertainties": [],
  "artifacts": [],
  "created_at": null,
  "updated_at": null
}
```

Notes
- version enables future migrations of the canonical model without breaking downstream agents.
- artifacts holds references to uploads and generated outputs.

2) API overview (MVP)
- Core resources: Projects; Ingestion; Processing; Outputs; Clarifications
- Endpoints (high level):
  - POST /projects
  - GET /projects/{project_id}
  - GET /projects/{project_id}/status
  - POST /projects/{project_id}/ingest/{type}
  - POST /projects/{project_id}/process
  - POST /projects/{project_id}/reprocess
  - GET /projects/{project_id}/context
  - GET /projects/{project_id}/files
  - GET /projects/{project_id}/files/{filename}
  - GET /projects/{project_id}/diagrams
  - GET /projects/{project_id}/questions
  - POST /projects/{project_id}/questions/answer
  - POST /projects/{project_id}/questions/clear

Payloads (illustrative)
- Ingestion (image):
  { "images": [ { "filename": "diagram1.png", "source": "http://...", "metadata": {} }, ... ] }
- Ingestion (text):
  { "texts": [ { "source": "manual", "content": "..." }, ... ] }
- Ingestion (repo):
  { "repos": [ { "repo_url": "https://public.repo/repo.git", "reference": "main" } ] }
- Ingestion (document):
  { "docs": [ { "filename": "spec.md", "source": "uploaded", "metadata": {} } ] }

Responses (typical)
- ingestion: { "ingest_id": "ingest_xyz", "status": "queued" }
- process: { "process_id": "proc_123", "status": "started" }
- context: { "project_id": "proj_1", "context": { ... } }

3) Ingestion pipelines (source-specific)
- Image pipeline
  - Preprocess: resize, denoise, contrast, deskew (OpenCV/Pillow)
  - Semantic signals: multModal model + optional OCR; detect components, arrows, labels, data stores, trust boundaries
  - Output signals: canonical blocks that map to Component, Flow, Dependency, InputSource structures
  - Uncertainty handling: mark uncertain labels; include in 07-open-questions.md

- Repo pipeline (public repos only for Phase 1)
  - Clone public repo
  - Infer languages/frameworks; inspect package manifests, Dockerfiles, infra clues
  - Inspect configs (docker-compose, k8s, env files); readme/docs for domain signals
  - Output: signals mapping to discovered components, dependencies, runtimes

- Text and Document pipelines
  - Normalize text; extract summary, explicit requirements, mentioned components/services, flows
  - Identify ambiguities/contradictions; output signals for normalization

4) Processing pipeline (Celery-based)
- Orchestrator task: normalize_signals
- Per-source tasks: ingest_image_signal, ingest_repo_signal, ingest_text_signal, ingest_document_signal
- Merge step: combine signals into one ProjectContext; deduplicate, resolve conflicts with confidences
- Clarifications: generate targeted questions for missing context; persist in model & 07-open-questions.md
- Rendering: produce Markdown files (01-08) and Mermaid diagrams; annotate uncertainties
- Persistence: store normalized context as JSON in Postgres; artifacts in MinIO/S3; processing runs & QA in Postgres

5) Graph outputs and migrations (no visuals)
- Markdown artifacts: 01-overview.md, 02-stack.md, 03-components.md, 04-dependencies.md, 05-flows.md, 06-assumptions.md, 07-open-questions.md
- Graph JSON artifacts: system_graph.json, flow_graph.json, deployment_hints.json
- Alembic migrations: 0001_initial.py creates core tables; migrations run via alembic upgrade head
- Migrations can also run on startup when MIGRATE_ON_STARTUP=1 is set
- Graph DSL artifacts: system_graph.dsl, flow_graph.dsl
- Graph DSL artifacts: system_graph.dsl, flow_graph.dsl
- No Mermaid/visual diagrams; no presentation-oriented diagram outputs in Phase 1

6) Storage and persistence design
- Metadata: Postgres (project, runs, questions/answers, context snapshot version)
- Artifacts/outputs: MinIO for local/dev; S3-compatible storage for live; via storage adapter
- Context pack: JSON payload stored and retrievable via /projects/{id}/context

7) Docker Compose dev stack (starter)
- Services: db (Postgres), redis (Celery broker), minio, api (FastAPI), celery (workers)
- Env placeholders for DB URL, broker URL, storage backend, MinIO endpoints, S3 credentials
- A minimal skeleton is provided in a follow-up patch for quick local testing

8) Project structure (starter outline)
- app/ with modules for api, core, domain, pipelines, renderers, adapters, workers, tests
- Patch plan will add a minimal scaffold later after design review

9) Validation plan
- Model schema validation using Pydantic; tests for defaults and basic integration contracts
- End-to-end tests using in-memory or stubbed adapters for ingestion endpoints
- Diagram rendering tests for valid Mermaid blocks

10) Next steps
- Produce a starter repository patch that adds: design doc, a minimal FastAPI skeleton, and a basic patch for docker-compose.yml
- Implement a minimal JSON context model, and a skeleton ingestion API (one endpoint per type)
- Add placeholder pipelines for image/repo/text/document that emit normalized signals to be consumed by the merger
- Add a simple renderer that writes 01-08.md skeletons and a simple 08-diagrams.md with Mermaid blocks

Appendix A: Sample ProjectContext (JSON)
```json
{
  "version": 1,
  "project_name": "Sample Project",
  "summary": "A sample project for end-to-end ingestion, normalization, and documentation.",
  "input_sources": [ {"id": "src1", "type": "image", "source": "https://example.com/diagram1.png", "metadata": {}} ],
  "stack": {
    "languages": ["Python"],
    "frameworks": ["FastAPI"],
    "databases": ["PostgreSQL"],
    "infrastructure": ["Docker"],
    "external_services": []
  },
  "components": [ {"name": "API Gateway", "type": "service", "description": "Entrypoint for clients", "responsibilities": ["auth", "routing"], "tech": ["FastAPI"], "depends_on": ["Postgres"], "exposes": ["/projects"] } ],
  "flows": [ {"name": "ingest_flow", "source": "ImageIngestor", "target": "Normalizer", "description": "image signals flow into normalizer", "confidence": 0.8 } ],
  "dependencies": [ {"name": "PostgreSQL", "type": "database", "role": "metadata_store", "confidence": 0.9 } ],
  "assumptions": ["Public repos only for Phase 1"],
  "open_questions": [],
  "uncertainties": [],
  "artifacts": [],
  "created_at": null,
  "updated_at": null
}
```

Notes on usage
- This document serves as a blueprint for implementation work in Phase 1 and will be updated as design decisions firm up.
- All patches moving forward will align with the canonical model and the API contract outlined here.

Detailed API contracts (OpenAPI-like)
- The API aims to be stable, with well-typed request/response bodies and clear error signaling.
- Core endpoints (MVP, detailed below):
- Projects: create, fetch, status
- Ingestion: per-type endpoints for image, text, repo, document
- Processing: start/restart processing
- Outputs: retrieve normalized context and diagrams
- Clarifications: fetch/list and answer questions

Example endpoints (illustrative OpenAPI-like spec)
- POST /projects
  - RequestBody: ProjectCreate
  - Response: ProjectInfo
- GET /projects/{project_id}
  - Response: ProjectInfo
- GET /projects/{project_id}/status
  - Response: { project_id, status }
- POST /projects/{project_id}/ingest/image
  - RequestBody: IngestImageRequest
  - Response: IngestResponse
- POST /projects/{project_id}/ingest/text
  - RequestBody: IngestTextRequest
  - Response: IngestResponse
- POST /projects/{project_id}/ingest/repo
  - RequestBody: IngestRepoRequest
  - Response: IngestResponse
- POST /projects/{project_id}/ingest/document
  - RequestBody: IngestDocumentRequest
  - Response: IngestResponse
- POST /projects/{project_id}/process
  - Response: ProcessingStatus
- GET /projects/{project_id}/context
  - Response: ContextResponse
- GET /projects/{project_id}/diagrams
  - Response: DiagramList
- GET /projects/{project_id}/questions
  - Response: List[Question]
- POST /projects/{project_id}/questions/answer
  - RequestBody: Answer
  - Response: AnswerAck
```
