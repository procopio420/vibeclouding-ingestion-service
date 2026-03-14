"""Source-agnostic extracted signals model.

This module defines a normalized signal structure that can be produced by any input source:
- repository (git clone)
- image (OCR/vision)
- text (pasted/documented)
- audio (transcription)

Layer C — Shared normalized signal model.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SourceMetadata(BaseModel):
    """Metadata about the source of extraction."""
    source_type: str  # repo, image, text, audio
    source_id: Optional[str] = None
    extraction_method: str  # heuristics, llm, ocr, transcription
    confidence: float = 1.0


class LanguageSignal(BaseModel):
    """Detected programming language."""
    name: str
    confidence: float = 1.0


class FrameworkSignal(BaseModel):
    """Detected framework."""
    name: str
    confidence: float = 1.0


class DatabaseSignal(BaseModel):
    """Detected database/cache service."""
    name: str
    type: str  # relational, document, cache, queue
    confidence: float = 1.0


class InfrastructureSignal(BaseModel):
    """Detected infrastructure component."""
    name: str  # Docker, Kubernetes, AWS, etc.
    category: str  # container, cloud, ci_cd, reverse_proxy
    confidence: float = 1.0


class ExternalServiceSignal(BaseModel):
    """Detected external service/API."""
    name: str
    category: str  # auth, payment, storage, analytics, etc.
    confidence: float = 1.0


class ComponentSignal(BaseModel):
    """Detected component within the project."""
    name: str
    component_type: str  # frontend, backend, worker, database, cache, queue, service
    description: Optional[str] = None
    technologies: List[str] = []
    detected_from: List[str] = []  # which source signals led to this detection
    confidence: float = 1.0


class FlowSignal(BaseModel):
    """Detected flow between components."""
    name: str
    source: str  # component name
    target: str  # component name
    flow_type: str  # http, data, message, file
    description: Optional[str] = None
    confidence: float = 1.0


class DependencySignal(BaseModel):
    """Detected external dependency."""
    name: str
    dependency_type: str  # package, service, infrastructure
    role: str  # runtime, dev, optional
    confidence: float = 1.0


class ExtractedSignals(BaseModel):
    """Source-agnostic normalized signals from any input modality.
    
    This is Layer C — the shared intermediate representation that all
    source extractors should produce, regardless of input type.
    
    Layer A: Raw source (repo URL, image file, text, audio)
    Layer B: Source-specific extraction (repo_parsers, image_parsers, etc.)
    Layer C: This normalized signal model
    Layer D: Canonical ProjectContext (final output)
    """
    version: int = 1
    
    project_name: str
    project_type: str  # api, frontend, fullstack, worker, library, unknown
    
    summary: str = ""
    source_metadata: SourceMetadata
    
    languages: List[LanguageSignal] = []
    frameworks: List[FrameworkSignal] = []
    databases: List[DatabaseSignal] = []
    infrastructure: List[InfrastructureSignal] = []
    external_services: List[ExternalServiceSignal] = []
    
    components: List[ComponentSignal] = []
    flows: List[FlowSignal] = []
    dependencies: List[DependencySignal] = []
    
    assumptions: List[str] = []
    open_questions: List[str] = []
    uncertainties: List[str] = []
    
    raw_signals: Dict[str, Any] = {}  # source-specific raw data for debugging
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump()


def signals_to_context_dict(signals: ExtractedSignals) -> Dict[str, Any]:
    """Convert ExtractedSignals to dict format expected by context normalizer.
    
    This bridges Layer C to Layer D.
    """
    return {
        "project_name": signals.project_name,
        "project_type": signals.project_type,
        "summary": signals.summary,
        "stack": {
            "languages": [l.name for l in signals.languages],
            "frameworks": [f.name for f in signals.frameworks],
            "databases": [d.name for d in signals.databases],
            "infrastructure": [i.name for i in signals.infrastructure],
            "external_services": [e.name for e in signals.external_services],
        },
        "components": [
            {
                "name": c.name,
                "type": c.component_type,
                "description": c.description or "",
                "tech": c.technologies,
            }
            for c in signals.components
        ],
        "flows": [
            {
                "name": f.name,
                "source": f.source,
                "target": f.target,
                "description": f.description or "",
                "confidence": f.confidence,
            }
            for f in signals.flows
        ],
        "dependencies": [
            {
                "name": d.name,
                "type": d.dependency_type,
                "role": d.role,
                "confidence": d.confidence,
            }
            for d in signals.dependencies
        ],
        "assumptions": signals.assumptions,
        "open_questions": signals.open_questions,
        "uncertainties": signals.uncertainties,
    }
