"""Data models for tickets and triage results."""

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    ACCESS = "access"
    NETWORK = "network"
    EMAIL = "email"
    ERP = "erp"
    OTHER = "other"


class Priority(str, Enum):
    P1 = "P1"  # business stopped, many users affected
    P2 = "P2"  # one team blocked or a critical system degraded
    P3 = "P3"  # one user affected, workaround exists
    P4 = "P4"  # request or question


class Ticket(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=10_000)
    requester: str | None = None
    department: str | None = None


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(max_length=300)
    suggested_reply: str = Field(max_length=2_000)
    needs_human: bool
    source: str = Field(description="'llm' or 'rules'")
    reasons: list[str] = Field(default_factory=list)


class LlmTriage(BaseModel):
    """The exact JSON shape the LLM must return. Anything else is rejected."""

    category: Category
    priority: Priority
    summary: str = Field(max_length=300)
    suggested_reply: str = Field(max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
