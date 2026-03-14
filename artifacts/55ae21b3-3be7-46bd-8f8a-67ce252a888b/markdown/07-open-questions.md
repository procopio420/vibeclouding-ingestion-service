# Open Questions

## Questions

1. What is the tenant isolation strategy (schema-level, database-level, or host-based)?
2. How are WhatsApp webhooks authenticated and rate-limited?
3. What is the database migration strategy?
4. How is the application containerized for deployment?
5. What is the deployment target (bare metal, k8s, serverless)?
6. How is multi-tenancy implemented (database, schema, or code-level)?
7. What environment variables are required for deployment?
8. What secrets need to be managed (API keys, database credentials)?
9. How are workers scaled (horizontal pod autoscaling, number of replicas)?
10. What happens when a job fails - retry policy?

## Uncertainties

1. No containerization detected - deployment approach unclear
2. No .env.example found - configuration management unclear
