# Change Log

- 2026-03-15: Discovery UI enrichment
  - GET /projects/{project_id}/context now returns a stable top-level payload enriched with understanding_summary and next_best_step for UI consumption.
  - New GET /projects/{project_id}/activity endpoint provides a lightweight activity feed.
  - Added API documentation for these enhancements under docs/API_DISCOVERY.md.
