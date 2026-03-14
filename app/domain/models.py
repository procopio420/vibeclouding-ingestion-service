from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class InputSource(BaseModel):
    id: str
    type: str  # image | repo | text | document
    source: str
    metadata: Dict[str, Any] = {}


class Stack(BaseModel):
    languages: List[str] = []
    frameworks: List[str] = []
    databases: List[str] = []
    infrastructure: List[str] = []
    external_services: List[str] = []


class Component(BaseModel):
    name: str
    type: str
    description: Optional[str] = ""
    responsibilities: List[str] = []
    tech: List[str] = []
    depends_on: List[str] = []
    exposes: List[str] = []
    consumes: List[str] = []


class Flow(BaseModel):
    name: str
    source: str
    target: str
    description: str
    confidence: float = 0.0


class Dependency(BaseModel):
    name: str
    type: str
    role: str
    confidence: float = 0.0


class ProjectContext(BaseModel):
    version: int = 1
    project_name: str
    summary: Optional[str] = ""
    input_sources: List[InputSource] = []
    stack: Stack = Stack()
    components: List[Component] = []
    flows: List[Flow] = []
    dependencies: List[Dependency] = []
    assumptions: List[str] = []
    open_questions: List[str] = []
    uncertainties: List[str] = []
    artifacts: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
