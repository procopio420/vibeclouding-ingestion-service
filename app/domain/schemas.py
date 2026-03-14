from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class InputSourceSchema(BaseModel):
    id: str
    type: str
    source: str
    metadata: Dict[str, Any] = {}


class StackSchema(BaseModel):
    languages: List[str] = []
    frameworks: List[str] = []
    databases: List[str] = []
    infrastructure: List[str] = []
    external_services: List[str] = []
