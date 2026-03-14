Discovery API Enhancement Migration Guide
=======================================

What changed
- The GET /projects/{project_id}/context endpoint now returns a stable top-level payload enriched with:
  - understanding_summary
  - next_best_step
- A new GET /projects/{project_id}/activity endpoint was added to expose an activity feed.
- No database schema changes were required; all changes are surfaced at the API layer and derived from existing data sources (consolidated context, checklist, lifecycle, readiness, and repository ingestion jobs).

Migration steps for API clients
- If you previously relied on the /projects/{project_id}/context response wrapping, update client code to consume the top-level keys directly (e.g., context.understanding_summary, context.next_best_step).
- Update UI wiring to read understanding_summary and next_best_step from the top-level context payload rather than from a nested context key.
- Add a call to GET /projects/{project_id}/activity to surface discovery events if you want to display an activity feed in your UI.
- If you cache the old shape, invalidate caches and re-fetch to obtain the enriched payloads.

Testing recommendations
- Manually exercise a sample project to verify: a) the new fields appear in the /context payload, b) the next_best_step payload is well-formed, and c) the activity feed surfaces open/answered lifecycle events and repo_ingest jobs.

Operational notes
- The API surface remains backwards-compatible for downstream code consuming the /context payload, given that the enrichment is additive and placed at the top level.
- If you want to deprecate the old shape in the future, plan a deprecation window and communicate it to consuming teams.
