# Flows

## api_to_database

**From:** api → **To:** database

API queries database via SQLAlchemy ORM

*Confidence:* 85%

## api_to_cache

**From:** api → **To:** cache

API uses Redis for caching and session storage

*Confidence:* 75%

## api_to_queue

**From:** api → **To:** cache

API enqueues jobs to Redis/RQ

*Confidence:* 80%

## worker_from_queue

**From:** cache → **To:** worker

Worker picks up jobs from Redis queue

*Confidence:* 80%

## worker_to_database

**From:** worker → **To:** database

Worker queries database for job processing

*Confidence:* 70%

## frontend_to_api

**From:** frontend → **To:** api

Frontend makes HTTP API requests

*Confidence:* 85%

## whatsapp_to_api

**From:** whatsapp_api → **To:** api

WhatsApp Cloud API sends webhooks to API

*Confidence:* 85%
