from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


# Core project creation payload
class ProjectCreate(BaseModel):
    project_name: str = Field(..., description="Human-friendly project name")
    summary: Optional[str] = Field(None, description="Short summary of the project")


class ProjectInfo(BaseModel):
    project_id: str
    status: str


class RevisionDecisionUpdate(BaseModel):
    decision: Literal["vibe_economica", "vibe_performance"] = Field(
        ..., description="Selected architecture vibe for terraform generation"
    )


class RevisionDecisionResponse(BaseModel):
    decision: Optional[str] = Field(
        None,
        description="Selected vibe: vibe_economica, vibe_performance, or null if not set",
    )


# Ingestion payloads (per-type)
class IngestImageItem(BaseModel):
    filename: Optional[str] = Field(None, description="Optional filename of the image artifact")
    source: str
    metadata: Dict[str, Any] = {}

class IngestImageRequest(BaseModel):
    images: List[IngestImageItem] = []


class IngestTextItem(BaseModel):
    content: str
    source: Optional[str] = Field("manual", description="Source descriptor")
    metadata: Dict[str, Any] = {}

class IngestTextRequest(BaseModel):
    texts: List[IngestTextItem] = []


class IngestRepoItem(BaseModel):
    repo_url: str
    reference: Optional[str] = "main"

class IngestRepoRequest(BaseModel):
    repos: List[IngestRepoItem] = []


class IngestDocumentItem(BaseModel):
    filename: Optional[str] = None
    source: str
    metadata: Dict[str, Any] = {}

class IngestDocumentRequest(BaseModel):
    docs: List[IngestDocumentItem] = []


class IngestResponse(BaseModel):
    ingest_id: str
    status: str
    project_id: str
    type: str


class ContextResponse(BaseModel):
    project_id: str
    context: dict
    status: str


class ErrorResponse(BaseModel):
    code: int
    message: str


class ArchitectureResultRequest(BaseModel):
    analise_entrada: Dict[str, Any] = Field(..., description="Analysis input/context")
    vibe_economica: Dict[str, Any] = Field(..., description="Economic/financial vibe analysis")
    vibe_performance: Dict[str, Any] = Field(..., description="Performance vibe analysis")


class ArchitectureResultResponse(BaseModel):
    architecture_result_id: str
    project_id: str
    schema_version: str
    analise_entrada: Any
    vibe_economica: Any
    vibe_performance: Any
    raw_payload_storage_key: Optional[str] = None
    status: str
    created_at: str


class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="User message content")
