"""Minimal FastAPI skeleton for Phase 1 ingestion & normalization"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers (MVP skeleton)
from app.api.routes import projects as projects_routes
from app.api.routes import ingest as ingest_routes
from app.api.routes import process as process_routes
from app.api.routes import outputs as outputs_routes
from app.api.routes import questions as questions_routes
from app.api.routes import jobs as jobs_routes
# Event contracts route (tiny in-memory event stub for Phase 3)
from app.api.routes import events as events_routes
# Architecture result routes
from app.api.routes import architecture as architecture_routes
# Discovery routes (REST)
from app.api.routes import discovery as discovery_routes
# Discovery WebSocket
from app.api.routes import discovery_ws as discovery_ws_routes

app = FastAPI(title="PDD Phase 1 - Ingestion & Normalization (Skeleton)")

# CORS middleware - allow all origins for WebSocket compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(projects_routes.router)
app.include_router(ingest_routes.router)
app.include_router(process_routes.router)
app.include_router(outputs_routes.router)
app.include_router(questions_routes.router)
app.include_router(jobs_routes.router)
app.include_router(events_routes.router)
app.include_router(architecture_routes.router)
app.include_router(discovery_routes.router)
app.include_router(discovery_ws_routes.router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "PDD Phase 1 API skeleton"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
