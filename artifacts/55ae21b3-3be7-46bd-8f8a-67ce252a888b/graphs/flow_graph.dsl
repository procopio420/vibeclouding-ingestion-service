// flow_graph.dsl - Generated from repo analysis
// Version: 1

// API queries database via SQLAlchemy ORM
flow api -> database "http"

// API uses Redis for caching and session storage
flow api -> cache "http"

// API enqueues jobs to Redis/RQ
flow api -> cache "http"

// Worker picks up jobs from Redis queue
flow cache -> worker "http"

// Worker queries database for job processing
flow worker -> database "http"

// Frontend makes HTTP API requests
flow frontend -> api "http"

// WhatsApp Cloud API sends webhooks to API
flow whatsapp_api -> api "http"
