"""Request / response schemas for the gateway API."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# --- Health ---


def _utc_now() -> datetime:
    return datetime.now(UTC)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=_utc_now)


# --- Chat / Work Orders ---


class Difficulty(StrEnum):
    trivial = "trivial"
    normal = "normal"
    complex = "complex"
    unclear = "unclear"


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=_utc_now)


class WorkOrder(BaseModel):
    id: str
    intent: str
    difficulty: Difficulty = Difficulty.normal
    owner: str | None = None
    compressed_context: str = ""
    relevant_files: list[str] = Field(default_factory=list)
    qa_requirements: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


# --- WebSocket frames ---


class WSFrameType(StrEnum):
    request = "req"
    response = "res"
    event = "event"


class WSRequest(BaseModel):
    type: str = "req"
    id: str
    method: str
    params: dict = Field(default_factory=dict)


class WSResponse(BaseModel):
    type: str = "res"
    id: str
    ok: bool
    payload: dict | None = None
    error: str | None = None


class WSEvent(BaseModel):
    type: str = "event"
    event: str
    payload: dict = Field(default_factory=dict)
    seq: int | None = None
