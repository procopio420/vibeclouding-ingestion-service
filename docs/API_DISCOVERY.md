Discovery API Enrichment for Richer UI
=====================================

Overview
- The Discovery API now returns a richer, more stable shape for the frontend Discovery UI.
- Enhancements include:
  - A stable top-level /projects/{project_id}/context payload (no wrapper object).
  - Understanding of what we already understand (understanding_summary).
  - The recommended next focus (next_best_step).
  - A new activity feed endpoint at /projects/{project_id}/activity.

New Endpoints
- GET /projects/{project_id}/context
  - Returns the consolidated context at the top level, enriched with:
    - understanding_summary: { items: [{ key, label, value, source }] }
    - next_best_step: { title, description, type }
  - Shape example:
    {
      "project": { ... },
      "overview": { ... },
      "stack": { ... },
      "components": [...],
      "dependencies": [...],
      "flows": [...],
      "assumptions": [...],
      "open_questions": [...],
      "uncertainties": [...],
      "graphs": { ... },
      "readiness": { ... },
      "artifacts": { ... },
      "understanding_summary": {
        "items": [
          {"key": "product_goal", "label": "What does your project do?", "value": "...", "source": "confirmed"},
          {"key": "target_users", "label": "Who are your target users?", "value": "...", "source": "inferred"}
        ]
      },
      "next_best_step": {
        "title": "Do you already have a GitHub repository for this project?",
        "description": "Verify whether a repository exists for the project.",
        "type": "repo"
      }
    }

- GET /projects/{project_id}/activity
  - Returns a lightweight event feed for the project:
  - Shape:
    {
      "events": [
        {"type": "question_open", "label": "What does your project do? Can you describe what problem it solves?", "timestamp": "2026-03-15T12:34:56Z"},
        {"type": "repo_ingest", "label": "Repo ingestion: 1234", "timestamp": "2026-03-15T13:00:00Z"}
      ]
    }

Data Contracts (Details)
- understanding_summary: { items: [{ key, label, value, source }] }
  - source is either "confirmed" or "inferred" to indicate how the value was derived.
- next_best_step: { title, description, type }
  - type can be: repo, question, clarification, review
- context shape stability
  - Project-level keys: project, overview, stack, components, dependencies, flows, assumptions, open_questions, uncertainties, graphs, readiness, understanding_summary
- activity events
  - Each event has: type, label, timestamp

Notes
- No changes to the underlying data model were required for this UI enrichment.
- The enrichment is computed on-the-fly when serving GET /projects/{project_id}/context.
