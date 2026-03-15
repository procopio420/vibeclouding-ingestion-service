"""WebSocket event schemas for discovery."""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ClientEventType(str, Enum):
    MESSAGE_CREATE = "message.create"
    SESSION_START = "session.start"
    CHECKLIST_UPDATE = "checklist.update"
    QUESTION_ANSWER = "question.answer"
    RESPONSE_CANCEL = "response.cancel"
    PING = "ping"


class ServerEventType(str, Enum):
    CONNECTION_READY = "connection.ready"
    HISTORY = "history"
    MESSAGE_ACCEPTED = "message.accepted"
    MESSAGE_CREATED = "message.created"
    ASSISTANT_RESPONSE_STARTED = "assistant.response.started"
    ASSISTANT_RESPONSE_DELTA = "assistant.response.delta"
    ASSISTANT_RESPONSE_COMPLETED = "assistant.response.completed"
    ASSISTANT_MESSAGE_CREATED = "assistant.message.created"
    SESSION_STARTED = "session.started"
    SESSION_STATE_CHANGED = "session.state_changed"
    CHECKLIST_UPDATED = "checklist.updated"
    CHECKLIST_PROGRESS = "checklist.progress"
    READINESS_UPDATED = "readiness.updated"
    QUESTION_ASKED = "question.asked"
    QUESTION_ANSWERED = "question.answered"
    RUN_STATUS = "run.status"
    DISCOVERY_PANEL_UPDATED = "discovery.panel_updated"
    ERROR = "error"
    PONG = "pong"


class RunStatus(str, Enum):
    IDLE = "idle"
    ACCEPTED = "accepted"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConnectionReadyData(BaseModel):
    client_id: str
    conversation_id: str
    session: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    checklist: List[Dict[str, Any]] = Field(default_factory=list)
    readiness: Dict[str, Any] = Field(default_factory=dict)
    questions: List[Dict[str, Any]] = Field(default_factory=list)


class MessageCreateData(BaseModel):
    project_id: str
    content: str


class ChecklistUpdateData(BaseModel):
    key: str
    status: str
    evidence: Optional[str] = None


class QuestionAnswerData(BaseModel):
    question_id: str
    answer: str


class ResponseCancelData(BaseModel):
    run_id: str


class MessageAcceptedData(BaseModel):
    user_message_id: str


class MessageCreatedData(BaseModel):
    id: str
    project_id: str
    role: str
    content: str
    message_type: Optional[str] = None
    created_at: Optional[str] = None


class AssistantResponseStartedData(BaseModel):
    run_id: str


class AssistantResponseDeltaData(BaseModel):
    run_id: str
    delta: str


class AssistantResponseCompletedData(BaseModel):
    run_id: str
    message_id: str
    content: str


class AssistantMessageCreatedData(BaseModel):
    id: str
    role: str
    content: str
    created_at: Optional[str] = None


class SessionStartedData(BaseModel):
    session: Dict[str, Any]


class SessionStateChangedData(BaseModel):
    old_state: str
    new_state: str


class ChecklistUpdatedData(BaseModel):
    key: str
    status: str
    evidence: Optional[str] = None


class ChecklistProgressData(BaseModel):
    completed: int
    total: int
    percentage: float


class ReadinessUpdatedData(BaseModel):
    status: str
    coverage: float
    missing: List[str] = Field(default_factory=list)


class QuestionAskedData(BaseModel):
    id: str
    question: str
    priority: Optional[str] = None
    reason: Optional[str] = None


class QuestionAnsweredData(BaseModel):
    id: str
    answer: str


class RunStatusData(BaseModel):
    run_id: str
    status: RunStatus
    message: Optional[str] = None


class ErrorData(BaseModel):
    code: str
    message: str


class ClientEvent(BaseModel):
    type: ClientEventType
    data: Dict[str, Any] = Field(default_factory=dict)


class ServerEvent(BaseModel):
    type: ServerEventType
    data: Dict[str, Any] = Field(default_factory=dict)
