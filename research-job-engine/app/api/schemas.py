import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import JobStatus

Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Topic


class CreateJobResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus


class JobResponse(BaseModel):
    job_id: uuid.UUID
    topic: str
    status: JobStatus
    stage: str | None
    attempt_count: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    report_available: bool


class SourceOut(BaseModel):
    url: str
    title: str | None


class ReportResponse(BaseModel):
    job_id: uuid.UUID
    content: str
    sources: list[SourceOut]
    created_at: datetime
